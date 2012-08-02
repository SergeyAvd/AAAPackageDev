import datetime

import json
import yaml
import plistlib

from sublime_lib.view import OutputPanel


class DumperProto(object):
    """Prototype class for data dumpers of different types.

        Classes derived from this class (and in this file) will be appended
        to the module's ``get`` variable (a dict) with ``self.ext`` as their key.

        Variables to be defined:

            name (str)
                The dumpers name, e.g. "JSON" or "Property List".

            ext (str)
                The default file extension.

            output_panel_name (str; optional)
                If this is specified it will be used as the output panel's
                reference name.
                Defaults to ``"aaa_package_dev"``.


        Methods to be implemented:

            write(self, data, *args, **kwargs)
                This is called when the actual parsing should happen.

                Data to write is defined in ``data``.
                The parsed data should be returned.
                To output problems, use ``self.output.write_line(str)``.
                The default self.dump function will catch excetions raised
                and print them via ``str()`` to the output.

                *args, **kwargs parameters are passed from
                ``load(self, *args, **kwargs)``. If you want to specify or
                process any options or optional parsing, use these.

            validate_data(self, data, *args, **kwargs) (optional)

                Called by self.dump. Please read the documentation for
                _validate_data in order to understand how this function works.

        Methods you can override/implement
        (please read their documentation/code to understand their purposes):

            _validate_data(self, data, funcs)

            dump(self, *args, **kwargs)
    """
    name = ""
    ext  = ""
    output_panel_name = "aaa_package_dev"

    def __init__(self, window, view, new_file_path, output=None, file_path=None, *args, **kwargs):
        """Guess what this does.
        """
        self.window = window
        self.view = view
        self.file_path = file_path or view.file_name()
        self.new_file_path = new_file_path

        if isinstance(output, OutputPanel):
            self.output = output
        elif window:
            self.output = OutputPanel(window, self.output_panel_name)

    def validate_data(self, data, *args, **kwargs):
        """To be implemented (optional).

            Must return the validated data object.

            Example:
                return self._validate_data(data, [
                    ((lambda x: isinstance(x, float), int),
                     (lambda x: isinstance(x, datetime.datetime), str))
                ]
        """
        pass

    def _validate_data(self, data, funcs):
        """Check for incompatible data recursively.

        ``funcs`` is supposed to be a set, or just iterable two times and
        represents two functions, one to test whether the data is invalid
        and one to validate it. Both functions accept one parameter:
        the object to test.

        Example:
            funcs = ((lambda x: isinstance(x, float), int),
                     (lambda x: isinstance(x, datetime.datetime), str))
        """
        checked = []

        def check_recursive(obj):
            if obj in checked:  # won't work for immutable types
                return
            checked.append(obj)

            for is_invalid, validate in funcs:
                if is_invalid(obj):
                    obj = validate(obj)

            if isinstance(obj, dict):  # dicts are fine
                for key in obj:
                    obj[key] = check_recursive(obj[key])

            if isinstance(obj, list):  # lists are too
                for i in range(len(obj)):
                    obj[i] = check_recursive(obj[i])

            if isinstance(obj, tuple):  # tuples are immutable ...
                return tuple([check_recursive(sub_obj) for sub_obj in obj])

            if isinstance(obj, set):  # sets ...
                for val in obj:
                    new_val = check_recursive(val)
                    if new_val != val:  # a set's components are hashable, no need to "is"
                        obj.remove(val)
                        obj.add(new_val)

            return obj

        return check_recursive(data)

    def dump(self, data, *args, **kwargs):
        """Wraps the ``self.write`` function.

        This function is called by the handler directly.
        """
        self.output.write_line("Writing %s... (%s)" % (self.name, self.new_file_path))
        self.output.show()
        data = self.validate_data(data)
        try:
            self.write(data, *args, **kwargs)
        except Exception, e:
            self.output.write_line("Error writing %s: %s" % (self.name, e))
        else:
            return True

    def write(self, data, *args, **kwargs):
        """To be implemented."""
        pass


class JSONDumper(DumperProto):
    name = "JSON"
    ext  = "json"

    def validate_data(self, data):
        return self._validate_data(data, [
            # TOTEST: sets
            (lambda x: isinstance(x, plistlib.Data), lambda x: x.data),  # plist
            (lambda x: isinstance(x, datetime.date), str),  # yaml
            (lambda x: isinstance(x, datetime.datetime), str)  # plist and yaml
        ])

    def write(self, data, *args, **kwargs):
        """Parameters:

            skipkeys (bool)
                Default: True

                Dict keys that are not of a basic type (str, unicode, int,
                long, float, bool, None) will be skipped instead of raising a
                TypeError.

            ensure_ascii (bool)
                Default: True

                If False, then some chunks may be unicode instances, subject to
                normal Python str to unicode coercion rules.

            check_circular (bool)
                Default: False

                If False, the circular reference check for container types will
                be skipped and a circular reference will result in an
                OverflowError (or worse).
                Since we are working with file data here this is likely not
                going to happen.

            allow_nan (bool)
                Default: True

                If False, it will be a ValueError to serialize out of range
                float values (nan, inf, -inf) in strict compliance of the JSON
                specification, instead of using the JavaScript equivalents
                (NaN, Infinity, -Infinity).

            indent (int)
                Default: 4

                If a non-negative integer, then JSON array elements and object
                members will be pretty-printed with that indent level. An
                indent level of 0 will only insert newlines. None (the default)
                selects the most compact representation.

            separators (tuple, iterable)
                Default: (', ', ': ')

                (item_separator, dict_separator) tuple. (',', ':') is the most
                compact JSON representation.

            encoding (str)
                Default: UTF-8

                Character encoding for str instances, default is UTF-8.
        """
        # Define default parameters
        json_params = dict(
                           skipkeys=True,
                           check_circular=False,  # there won't be references here, hopefully
                           indent=4,
                           sort_keys=True
                          )
        json_params.update(kwargs)

        with open(self.new_file_path, "w") as f:
            json.dump(data, f, **json_params)


class PlistDumper(DumperProto):
    name = "Property List"
    ext  = "plist"

    def validate_data(self, data):
        return self._validate_data(data, [
            # TOTEST: sets
            # yaml; lost of precision when converting to datetime.datetime
            (lambda x: isinstance(x, datetime.date), str),
            (lambda x: x is None, False)
        ])

    def write(self, data):
        plistlib.writePlist(data, self.new_file_path)


class YAMLDumper(DumperProto):
    name = "YAML"
    ext  = "yaml"

    def validate_data(self, data):
        return self._validate_data(data, [
            # plistlib defines its own dict wrapper,
            # yaml.safe_dump only dumps "dict" type ...
            (lambda x: isinstance(x, plistlib._InternalDict), dict),
            (lambda x: isinstance(x, plistlib.Data), lambda x: x.data)  # plist
        ])

    def write(self, data, *args, **kwargs):
        """Parameters:

            default_style (str)
                Default: None
                Accepted: None, '', '\'', '"', '|', '>'.

                Indicates the style of the scalar.

            default_flow_style (bool)
                Default: True

                Indicates if a collection is block or flow.

            canonical (bool)
                Default: None (-> False)

                Export tag type to the output file.

            indent (int)
                Default: 2
                Accepted: 1 < x < 10

            width (int)
                Default: 80
                Accepted: > indent*2

            allow_unicode (bool)
                Default: None (-> False)

            line_break (str)
                Default: "\n"
                Accepted: u'\r', u'\n', u'\r\n'

            encoding (str)
                Default: 'utf-8'

            explicit_start (bool)
                Default: None (-> False)

                Explicit '---' at the start.

            explicit_end (bool)
                Default: None (-> False)

                Excplicit '...' at the end.

            version (tuple)
                Default: Newest

                Version of the YAML parser: tuple(major, minor).
                Supports only major version 1.

            tags (str?)
                Default: None

                ???
        """
        with open(self.new_file_path, "w") as f:
            yaml.safe_dump(data, f, **kwargs)


###############################################################################


# Collect all the dumpers and assign them to `get`
get = dict()
for type_name in dir():
    try:
        t = globals()[type_name]
        if t.__bases__:
            is_plugin = False
            if issubclass(t, DumperProto) and not t is DumperProto:
                get[t.ext] = t

    except AttributeError:
        pass