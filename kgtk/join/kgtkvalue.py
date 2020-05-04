"""
Validate KGTK File data types.

Dimensioned quantities are not supported.

"""

from argparse import ArgumentParser, Namespace
import attr
import iso639 # type: ignore
import pycountry # type: ignore
import re
import sys
import typing

from kgtk.join.kgtkformat import KgtkFormat

DEFAULT_ADDITIONAL_LANGUAGE_CODES: typing.List[str] = [
    "mo", # Retired, replaced by the codes for Romanian, but still appearing in wikidata.
]


@attr.s(slots=True, frozen=True)
class KgtkValueOptions:
    """
    These options will affect some aspects of value processing. They are in a
    seperate class for efficiency.
    """
    
    # Allow month 00 or day 00 in dates?  This isn't really allowed by ISO
    # 8601, but appears in wikidata.
    allow_month_or_day_zero: bool = attr.ib(validator=attr.validators.instance_of(bool), default=False)

    # When allow_lax_strings is true, strings will be checked to see if they
    # start and end with double quote ("), but we won't check if internal
    # double quotes are excaped by backslash.
    allow_lax_strings: bool = attr.ib(validator=attr.validators.instance_of(bool), default=False)

    # When allow_lax_lq_strings is true, language qualified strings will be
    # checked to see if they start and end with single quote ('), but we won't
    # check if internal single quotes are excaped by backslash.
    allow_lax_lq_strings: bool = attr.ib(validator=attr.validators.instance_of(bool), default=False)
    
    # Shall we allow additional language codes?
    allow_additional_language_codes: bool = attr.ib(validator=attr.validators.instance_of(bool), default=False)

    # If this list gets long, we may want to turn it into a map to make lookup
    # more efficient.
    additional_language_codes: typing.List[str] = attr.ib(validator=attr.validators.deep_iterable(member_validator=attr.validators.instance_of(str),
                                                                                                  iterable_validator=attr.validators.instance_of(list)),
                                                          default=DEFAULT_ADDITIONAL_LANGUAGE_CODES)
    

    @classmethod
    def add_arguments(cls, parser: ArgumentParser):
        parser.add_argument(      "--additional-language-codes", dest="additional_language_codes",
                                  help="Additional language codes.", nargs="*", default=DEFAULT_ADDITIONAL_LANGUAGE_CODES)

        parser.add_argument(      "--allow-additional-language-codes", dest="allow_additional_language_codes",
                                  help="Allow certain language codes not found in the current version of ISO 639-3 or ISO 639-5.", action='store_true')

        parser.add_argument(      "--allow-lax-strings", dest="allow_lax_strings",
                                  help="Do not check if double quotes are backslashed inside strings.", action='store_true')

        parser.add_argument(      "--allow-lax-lq-strings", dest="allow_lax_lq_strings",
                                  help="Do not check if single quotes are backslashed inside language qualified strings.", action='store_true')

        parser.add_argument(      "--allow-month-or-day-zero", dest="allow_month_or_day_zero",
                                  help="Allow month or day zero in dates.", action='store_true')

    @classmethod
    # Build the value parsing option structure.
    def from_args(cls, args: Namespace)->'KgtkValueOptions':
        return cls(allow_month_or_day_zero=args.allow_month_or_day_zero,
                   allow_lax_strings=args.allow_lax_strings,
                   allow_lax_lq_strings=args.allow_lax_lq_strings,
                   allow_additional_language_codes=args.allow_additional_language_codes,
                   additional_language_codes=args.additional_language_codes)

DEFAULT_KGTK_VALUE_OPTIONS: KgtkValueOptions = KgtkValueOptions()

@attr.s(slots=True, frozen=False)
class KgtkValue(KgtkFormat):
    value: str = attr.ib(validator=attr.validators.instance_of(str))
    options: KgtkValueOptions = attr.ib(validator=attr.validators.instance_of(KgtkValueOptions), default=DEFAULT_KGTK_VALUE_OPTIONS)

    split_list_re: typing.Pattern = re.compile(r"(?<!\\)" + "\\" + KgtkFormat.LIST_SEPARATOR)

    # Cache the list of values.  This member is why the class isn't frozen.
    values: typing.Optional[typing.List[str]] = None

    def get_list(self)->typing.List[str]:
        if self.values is None:
            self.values = KgtkValue.split_list_re.split(self.value)
        return self.values

    def get_item(self, idx: typing.Optional[int])-> str:
        if idx is None:
            return self.value
        else:
            return self.get_list()[idx]

    def is_list(self)->bool:
        return len(self.get_list()) > 1

    def get_values(self)->typing.List['KgtkValue']:
        """
        Convert the value into a list of KgtkValues.
        """
        if not self.is_list:
            return [ self ]
        else:
            result: typing.List['KgtkValue'] = [ ]
            v: str
            for v in self.get_list():
                result.append(KgtkValue(v, options=self.options))
            return result

    def is_empty(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the value is empty.
        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        return len(v) == 0

    def is_number_old(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is 0-9,+,-,. .
        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        return v.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "+", "-", "."))
    
    def is_valid_number_old(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is 0-9,_,-,.
        and Python can parse it.

        Examples:
        1
        123
        -123
        +123
        0b101
        0o277
        0x24F
        .4
        0.4
        10.
        10.4
        10.4e10
        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        if not v.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "+", "-", ".")):
            return False
        try:
            i: int = int(v, 0) # The 0 allows prefixes: 0b, 0o, and 0x.
            return True
        except ValueError:
            try:
                f: float = float(v)
                return True
            except ValueError:
                return False
        
    
    def is_number_or_quantity(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is 0-9,+,-,. .
        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        return v.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "+", "-", "."))
    
    # The following lexical analysis is based on:
    # https://docs.python.org/3/reference/lexical_analysis.html

    # The long integer suffix was part of Python 2.  It was dropped in Python 3.
    long_suffix_pat: str = r'[lL]'

    plus_or_minus_pat: str = r'[-+]'

    # Integer literals.
    #
    # Decimal integers, allowing leading zeros.
    digit_pat: str = r'[0-9]'
    decinteger_pat: str = r'(?:{digit}(?:_?{digit})*{long_suffix}?)'.format(digit=digit_pat,
                                                                            long_suffix=long_suffix_pat)
    bindigit_pat: str = r'[01]'
    bininteger_pat: str = r'(?:0[bB](":_?{bindigit})+{long_suffix})'.format(bindigit=bindigit_pat,
                                                                            long_suffix=long_suffix_pat)
    octdigit_pat: str = r'[0-7]'
    octinteger_pat: str = r'(?:0[oO](":_?{octdigit})+{long_suffix})'.format(octdigit=octdigit_pat,
                                                                            long_suffix=long_suffix_pat)
    hexdigit_pat: str = r'[0-7a-fA-F]'
    hexinteger_pat: str = r'(?:0[xX](":_?{hexdigit})+{long_suffix})'.format(hexdigit=hexdigit_pat,
                                                                            long_suffix=long_suffix_pat)
     
    integer_pat: str = r'(?:{decinteger}|{bininteger}|{octinteger}|{hexinteger})'.format(decinteger=decinteger_pat,
                                                                                        bininteger=bininteger_pat,
                                                                                        octinteger=octinteger_pat,
                                                                                        hexinteger=hexinteger_pat)

    # Floating point literals.
    digitpart_pat: str = r'(?:{digit}(?:_?{digit})*)'.format(digit=digit_pat)
    fraction_pat: str = r'(?:\.{digitpart})'.format(digitpart=digitpart_pat)
    pointfloat_pat: str = r'(?:{digitpart}?{fraction})|(?:{digitpart}\.)'.format(digitpart=digitpart_pat,
                                                                                 fraction=fraction_pat)
    exponent_pat: str = r'(?:[eE]{plus_or_minus}?{digitpart})'.format(plus_or_minus=plus_or_minus_pat,
                                                                      digitpart=digitpart_pat)
    exponentfloat_pat: str = r'(?:{digitpart}|{pointfloat}){exponent}'.format(digitpart=digitpart_pat,
                                                                              pointfloat=pointfloat_pat,
                                                                              exponent=exponent_pat)
    floatnumber_pat: str = r'(?:{pointfloat}|{exponentfloat})'.format(pointfloat=pointfloat_pat,
                                                                      exponentfloat=exponentfloat_pat)

    # Imaginary literals.
    imagnumber_pat: str = r'(?:{floatnumber}|{digitpart})[jJ]'.format(floatnumber=floatnumber_pat,
                                                                      digitpart=digitpart_pat)

    # Numeric literals.
    numeric_pat: str = r'(?:{plus_or_minus}?(?:{integer}|{floatnumber}|{imagnumber}))'.format(plus_or_minus=plus_or_minus_pat,
                                                                                              integer=integer_pat,
                                                                                              floatnumber=floatnumber_pat,
                                                                                              imagnumber=imagnumber_pat)

    # Tolerances
    tolerance_pat: str = r'(?:\[{numeric},{numeric}\])'.format(numeric=numeric_pat)

    # SI units taken from:
    # http://www.csun.edu/~vceed002/ref/measurement/units/units.pdf
    #
    # Note: if Q were in this list, it would conflict with Wikidata nodes (below).
    si_unit_pat: str = r'(?:m|kg|s|C|K|mol|cd|F|M|A|N|ohms|V|J|Hz|lx|H|Wb|V\W|Pa)'
    si_power_pat: str = r'(?:-1|2|3)' # Might need more.
    si_combiner_pat: str = r'[./]'
    si_pat: str = r'(?:{si_unit}{si_power}?(?:{si_combiner}{si_unit}{si_power}?)*)'.format(si_unit=si_unit_pat,
                                                                                           si_combiner=si_combiner_pat,
                                                                                           si_power=si_power_pat)
    # Wikidata nodes (for units):
    nonzero_digit_pat: str = r'[1-9]'
    wikidata_node_pat: str = r'(?:Q{nonzero_digit}{digit}*)'.format(nonzero_digit=nonzero_digit_pat,
                                                                    digit=digit_pat)

    units_pat: str = r'(?:{si}|{wikidata_node})'.format(si=si_pat,
                                                        wikidata_node=wikidata_node_pat)
    

    # This definition matches numbers or quantities.
    number_or_quantity_pat: str = r'{numeric}{tolerance}?{units}?'.format(numeric=numeric_pat,
                                                                          tolerance=tolerance_pat,
                                                                          units=units_pat)
    # This definition for quantity excludes plain numbers.
    quantity_pat: str = r'{numeric}(?:(?:{tolerance}{units}?)|{units})'.format(numeric=numeric_pat,
                                                                               tolerance=tolerance_pat,
                                                                               units=units_pat)
    # This matches numbers or quantities.
    number_or_quantity_re: typing.Pattern = re.compile(r'^' + number_or_quantity_pat + r'$')

    # This matches numbers but not quantities.
    number_re: typing.Pattern = re.compile(r'^' + numeric_pat + r'$')

    # This matches quantities excluding numbers.
    quantity_re: typing.Pattern = re.compile(r'^' + quantity_pat + r'$')

    def is_valid_number_or_quantity(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is 0-9,_,-,.
        and it is either a Python-compatible number or an enhanced
        quantity.
        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        if not v.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "+", "-", ".")):
            return False

        m: typing.Optional[typing.Match] = KgtkValue.number_or_quantity_re.match(v)
        return m is not None
        
    
    def is_valid_number(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is 0-9,_,-,.
        and it is a Python-compatible number (with optional limited enhancements).

        Examples:
        1
        123
        -123
        +123
        0b101
        0o277
        0x24F
        .4
        0.4
        10.
        10.4
        10.4e10
        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        if not v.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "+", "-", ".")):
            return False

        m: typing.Optional[typing.Match] = KgtkValue.number_re.match(v)
        return m is not None
        
    
    def is_valid_quantity(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is 0-9,_,-,.
        and it is an enhanced quantity.
        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        if not v.startswith(("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "+", "-", ".")):
            return False

        m: typing.Optional[typing.Match] = KgtkValue.quantity_re.match(v)
        return m is not None
        
    
    def is_string(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character  is '"'.

        Strings begin and end with double quote (").  Any internal double
        quotes must be escaped with backslash (\").  Triple-double quoted
        strings are not supported by KGTK File Vormat v2.

        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        return v.startswith('"')

    lax_string_re: typing.Pattern = re.compile(r'^".*"$')
    strict_string_re: typing.Pattern = re.compile(r'^"(?:[^"\\]|\\.)*"$')

    def is_valid_string(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character  is '"',
        the last character is '"', and any internal '"' characters are
        escaped by backslashes.
        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        if not v.startswith('"'):
            return False
        m: typing.Optional[typing.Match]
        if self.options.allow_lax_strings:
            m = KgtkValue.lax_string_re.match(v)
        else:
            m = KgtkValue.strict_string_re.match(v)
        return m is not None

    def is_structured_literal(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character  is ^@'!.
        """
        if self.is_list() and idx is None:
            return False
        
        v: str = self.get_item(idx)
        return v.startswith(("^", "@", "'", "!"))

    def is_symbol(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if not a number, string, nor structured literal.
        """
        if self.is_list() and idx is None:
            return False

        return not (self.is_number_or_quantity(idx) or self.is_string(idx) or self.is_structured_literal(idx))

    def is_boolean(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the value matches one of the special boolean symbols..
        """
        if self.is_list() and idx is None:
            return False

        v: str = self.get_item(idx)
        return v == KgtkFormat.TRUE_SYMBOL or v == KgtkFormat.FALSE_SYMBOL

    
    def is_language_qualified_string(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is '
        """
        if self.is_list() and idx is None:
            return False

        v: str = self.get_item(idx)
        return v.startswith("'")

    # Support two or three character language codes.  Suports hyphenated codes
    # with country codes or dialect names after a language code.
    lax_language_qualified_string_re: typing.Pattern = re.compile(r"^(?P<string>'.*')@(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z]+)?)$")
    strict_language_qualified_string_re: typing.Pattern = re.compile(r"^(?P<string>'(?:[^'\\]|\\.)*')@(?P<lang>[a-zA-Z]{2,3}(?:-[a-zA-Z]+)?)$")

    def is_valid_language_qualified_string(self, idx: typing.Optional[int] = None)->bool:
        """Return False if this value is a list and idx is None.
        Otherwise, return True if the value looks like a language-qualified string.

        The language code may be a two- or three-character code from ISO
        639-3, which replaces ISO 639-1 and ISO 639-2.  In addition, wikidata
        may include language codes, such as 'mo', that have been retired.  The
        additional_language_codes table supports these codes, when allowed.

        Wikidata may also contain collective language codes, such as "nah",
        referring the the Nahuatl languages. These codes from ISO 639-5 are
        accepted as a fallback when ISO 639-3 lookup fails.

        https://meta.wikimedia.org/wiki/Special_language_codes
        https://en.wikipedia.org/wiki/Template:ISO_639_name_be-tarask

        """
        if self.is_list() and idx is None:
            return False

        v: str = self.get_item(idx)
        # print("checking %s" % v)
        m: typing.Optional[typing.Match]
        if self.options.allow_lax_lq_strings:
            m = KgtkValue.lax_language_qualified_string_re.match(v)
        else:
            m = KgtkValue.strict_language_qualified_string_re.match(v)
        if m is None:
            # print("match failed for %s" % v)
            return False

        # Validate the language code:
        lang: str = m.group("lang").lower()
        # print("lang: %s" % lang)

        if len(lang) == 2:
            # Two-character language codes.
            if pycountry.languages.get(alpha_2=lang) is not None:
                return True

        elif len(lang) == 3:
            # Three-character language codes.
           if pycountry.languages.get(alpha_3=lang) is not None:
               return True

           # Perhaps this is a collective (language family) code from ISO 639-5?
           try:
               iso639.languages.get(part5=lang)
               return True
           except KeyError:
               pass

        # Wikidata contains entries such as:
        # 'panamenha'@pt-br      # language code followed by country code
        # 'Ecuador'@es-formal    # language code followed by dialect name
        #
        # If we see a dash, we'll check the language code by itself.
        # save_lang: str = lang # for the debug print below.
        country_or_dialect: str = ""
        if "-" in lang:
            (lang, country_or_dialect) = lang.split("-", 1)

            # TODO: refactor so this code isn't duplicated?
            if len(lang) == 2:
                # Two-character language codes.
                if pycountry.languages.get(alpha_2=lang) is not None:
                    return True

            elif len(lang) == 3:
                # Three-character language codes.
                if pycountry.languages.get(alpha_3=lang) is not None:
                    return True

            # Perhaps this is a collective (language family) code from ISO 639-5?
            try:
                iso639.languages.get(part5=lang)
                return True
            except KeyError:
                pass

        # If there's a table of additional language codes, check there:
        if self.options.allow_additional_language_codes and lang in self.options.additional_language_codes:
            return True

        # print("save_lang: %s lang: %s country_or_dialect: %s" % (save_lang, lang, country_or_dialect))
        return False

    def is_location_coordinates(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is @
        """
        if self.is_list() and idx is None:
            return False

        v: str = self.get_item(idx)
        return v.startswith("@")

    #location_coordinates_re: typing.Pattern = re.compile(r"^@(?P<lat>[-+]?\d{3}\.\d{5})/(?P<lon>[-+]?\d{3}\.\d{5})$")
    location_coordinates_re: typing.Pattern = re.compile(r"^@(?P<lat>[-+]?(?:\d+(?:\.\d*)?)|(?:\.\d+))/(?P<lon>[-+]?(?:\d+(?:\.\d*)?)|(?:\.\d+))$")

    def is_valid_location_coordinates(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the value looks like valid location coordinates.

        Note: The coordinates must look exactly like the examples in KGTK
        File Format v2, excelt for optional +/- characters.

        @043.26193/010.92708
        """
        if self.is_list() and idx is None:
            return False

        v: str = self.get_item(idx)
        m: typing.Optional[typing.Match] = KgtkValue.location_coordinates_re.match(v)
        if m is None:
            return False

        # Latitude runs from -90 to +90
        latstr: str = m.group("lat")
        try:
            lat: float = float(latstr)
            if  lat < -90. or lat > 90.:
                return False
        except ValueError:
            return False

        # Longitude runs from -180 to +180
        lonstr: str = m.group("lon")
        try:
            lon: float = float(lonstr)
            if lon < -180. or lon > 180.:
                return False
        except ValueError:
            return False

        return True

    def is_date_and_times(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is ^
        """
        if self.is_list() and idx is None:
            return False

        v: str = self.get_item(idx)
        return v.startswith("^")

    # This pattern allows month 00 and day 00, which are excluded by ISO 8601.
    lax_date_and_times_re: typing.Pattern = re.compile(r"^\^(?P<year>[0-9]{4})(?:(?P<hyphen>-)?(?P<month>1[0-2]|0[0-9])(?:(?(hyphen)-)(?P<day>3[01]|0[0-9]|[12][0-9])))T(?P<hour>2[0-3]|[01][0-9])(?:(?(hyphen):)(?P<minute>[0-5][0-9])(?:(?(hyphen):)(?P<second>[0-5][0-9])))(?P<zone>Z|\[-+][0-9][0-9](?::[0-9][0-9])?)?(?P<precision>/[0-1]?[0-9])?$")

    strict_date_and_times_re: typing.Pattern = re.compile(r"^\^(?P<year>[0-9]{4})(?:(?P<hyphen>-)?(?P<month>1[0-2]|0[1-9])(?:(?(hyphen)-)(?P<day>3[01]|0[1-9]|[12][0-9])))T(?P<hour>2[0-3]|[01][0-9])(?:(?(hyphen):)(?P<minute>[0-5][0-9])(?:(?(hyphen):)(?P<second>[0-5][0-9])))(?P<zone>Z|\[-+][0-9][0-9](?::[0-9][0-9])?)?(?P<precision>/[0-1]?[0-9])?$")

    def is_valid_date_and_times(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the value looks like valid date and times
        literal based on ISO-8601.

        Valid date formats:
        YYYY
        YYYY-MM
        YYYYMMDD
        YYYY-MM-DD

        Valid date and time formats
        YYMMDDTHH
        YYYY-MM-DDTHH
        YYMMDDTHHMM
        YYYY-MM-DDTHH:MM
        YYMMDDTHHMMSS
        YYYY-MM-DDTHH:MM:SS

        Optional Time Zone suffix for date and time:
        Z
        +HH
        -HH
        +HHMM
        -HHMM
        +HH:MM
        -HH:MM

        NOTE: This code also accepts the following, which are disallowed by the standard:
        YYYYT...
        YYYYMM
        YYYYMMT...
        YYYY-MMT...

        Note:  IS0-8601 disallows 0 for month or day, e.g.:
        Invalid                   Correct
        1960-00-00T00:00:00Z/9    1960-01-01T00:00:00Z/9

        TODO: Support fractional time elements

        TODO: Support week dates.

        TODO: Support ordinal dates

        TODO: Support Unicode minus sign as well as ASCII minus sign.

        TODO: validate the calendar date, eg fail if 31-Apr-2020.
        """
        if self.is_list() and idx is None:
            return False

        v: str = self.get_item(idx)
        m: typing.Optional[typing.Match]
        if self.options.allow_month_or_day_zero:
            m = KgtkValue.lax_date_and_times_re.match(v)
        else:
            m = KgtkValue.strict_date_and_times_re.match(v)
        return m is not None

    def is_extension(self,  idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the first character is !
        """
        if self.is_list() and idx is None:
            return False

        v: str = self.get_item(idx)
        return v.startswith("!")

        
    def is_valid_literal(self, idx: typing.Optional[int] = None)->bool:
        """
        Return False if this value is a list and idx is None.
        Otherwise, return True if the value looks like a valid literal.
        """
        if self.is_list() and idx is None:
            return False

        if self.is_string(idx):
            return self.is_valid_string(idx)
        elif self.is_number_or_quantity(idx):
            return self.is_valid_number_or_quantity(idx)
        elif self.is_structured_literal(idx):
            if self.is_language_qualified_string(idx):
                return self.is_valid_language_qualified_string(idx)
            elif self.is_location_coordinates(idx):
                return self.is_valid_location_coordinates(idx)
            elif self.is_date_and_times(idx):
                return self.is_valid_date_and_times(idx)
            elif self.is_extension(idx):
                return False # no validation presently available.
            else:
                return False # Shouldn't get here.
        else:
            return False

    def is_valid_item(self, idx: typing.Optional[int] = None)->bool:
        if self.is_list() and idx is None:
            return False

        if self.is_empty(idx):
            return True
        elif self.is_valid_literal(idx):
            return True
        else:
            return self.is_symbol(idx) # Should always be True

    def is_valid(self)->bool:
        """
        Is this a valid KGTK cell value?  If the value is a list, are all the
        components valid?
        """        
        result: bool = True
        kv: KgtkValue
        for kv in self.get_values():
            result = result and kv.is_valid_item()
        return result

    def describe(self, idx: typing.Optional[int] = None)->str:
        """
        Return a string that describes the value.
        """
        if self.is_list() and idx is None:
            result: str = ""
            kv: KgtkValue
            first: bool = True
            for kv in self.get_values():
                if first:
                    first = not first
                else:
                    result += KgtkFormat.LIST_SEPARATOR
                result += kv.describe()
            return result

        if self.is_empty(idx):
            return "Empty"
        elif self.is_string(idx):
            if self.is_valid_string(idx):
                return "String"
            else:
                return "Invalid String"
        elif self.is_number_or_quantity(idx):
            if self.is_valid_number(idx):
                return "Number"
            elif self.is_valid_quantity(idx):
                return "Quantity"
            else:
                return "Invalid Number or Quantity"
        elif self.is_structured_literal(idx):
            if self.is_language_qualified_string(idx):
                if self.is_valid_language_qualified_string(idx):
                    return "Language Qualified String"
                else:
                    return "Invalid Language Qualified String"
            elif self.is_location_coordinates(idx):
                if self.is_valid_location_coordinates(idx):
                    return "Location Coordinates"
                else:
                    return "Invalid Location Coordinates"
            elif self.is_date_and_times(idx):
                if self.is_valid_date_and_times(idx):
                    return "Date and Times"
                else:
                    return "Invalid Date and Times"
            elif self.is_extension(idx):
                return "Extension (unvalidated)"
            else:
                return "Invalid Structured Literal"
        else:
            return "Symbol"

    
def main():
    """
    Test the KGTK value vparser.
    """
    parser: ArgumentParser = ArgumentParser()
    parser.add_argument(dest="values", help="The values(s) to test", type=str, nargs="+")
    parser.add_argument("-v", "--verbose", dest="verbose", help="Print additional progress messages.", action='store_true')
    parser.add_argument(      "--very-verbose", dest="very_verbose", help="Print additional progress messages.", action='store_true')
    KgtkValueOptions.add_arguments(parser)
    args: Namespace = parser.parse_args()

    # Build the value parsing option structure.
    value_options: KgtkValueOptions = KgtkValueOptions.from_args(args)

    value: str
    for value in args.values:
        print("%s: %s" % (value, KgtkValue(value, options=value_options).describe()), flush=True)

if __name__ == "__main__":
    main()