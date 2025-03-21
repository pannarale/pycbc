# Copyright (C) 2015 Ian Harry, Tito Dal Canton
#               2022 Shichao Wu
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Generals
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""
This modules contains extensions for use with argparse
"""

import copy
import warnings
import argparse
import re
import math
from collections import defaultdict


class DictWithDefaultReturn(defaultdict):
    default_set = False
    ifo_set = False
    def __bool__(self):
        if self.items() and not all(entry is None for entry in self.values()):
            # True if any values are explictly set.
            return True
        elif self['RANDOM_STRING_314324'] is not None:
            # Or true if the default value was set
            # NOTE: This stores the string RANDOM_STRING_314324 in the dict
            # so subsequent calls will be caught in the first test here.
            return True
        else:
            # Else false
            return False
    # Python 2 and 3 have different conventions for boolean method
    __nonzero__ = __bool__

class MultiDetOptionAction(argparse.Action):
    # Initialise the same as the standard 'append' action
    def __init__(self,
                 option_strings,
                 dest,
                 nargs='+',
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None):
        if type is not None:
            self.internal_type = type
        else:
            self.internal_type = str
        new_default = DictWithDefaultReturn(lambda: default)
        #new_default.default_value=default
        if nargs == 0:
            raise ValueError('nargs for append actions must be > 0; if arg '
                             'strings are not supplying the value to append, '
                             'the append const action may be more appropriate')
        if const is not None and nargs != argparse.OPTIONAL:
            raise ValueError('nargs must be %r to supply const'
                             % argparse.OPTIONAL)
        super(MultiDetOptionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=new_default,
            type=str,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        # Again this is modified from the standard argparse 'append' action
        err_msg = "Issue with option: %s \n" %(self.dest,)
        err_msg += "Received value: %s \n" %(' '.join(values),)
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, DictWithDefaultReturn())
        items = getattr(namespace, self.dest)
        items = copy.copy(items)
        for value in values:
            value = value.split(':')
            if len(value) == 2:
                # "Normal" case, all ifos supplied independently as "H1:VALUE"
                if items.default_set:
                    err_msg += "If you are supplying a value for all ifos, you "
                    err_msg += "cannot also supply values for specific ifos."
                    raise ValueError(err_msg)
                items[value[0]] = self.internal_type(value[1])
                items.ifo_set = True
            elif len(value) == 1:
                # OR supply only one value and use this for all ifos
                if items.default_set:
                    err_msg += "If you are supplying a value for all ifos, you "
                    err_msg += "must only supply one value."
                    raise ValueError(err_msg)
                # Can't use a global and ifo specific options
                if items.ifo_set:
                    err_msg += "If you are supplying a value for all ifos, you "
                    err_msg += "cannot also supply values for specific ifos."
                    raise ValueError(err_msg)
                #items.default_value = self.internal_type(value[0])
                new_default = self.internal_type(value[0])
                items.default_factory = lambda: new_default
                items.default_set = True
            else:
                err_msg += "The character ':' is used to deliminate the "
                err_msg += "ifo and the value. Please do not use it more than "
                err_msg += "once."
                raise ValueError(err_msg)
        setattr(namespace, self.dest, items)

class MultiDetOptionActionSpecial(MultiDetOptionAction):
    """
    This class in an extension of the MultiDetOptionAction class to handle
    cases where the : is already a special character. For example the channel
    name is something like H1:CHANNEL_NAME. Here the channel name *must*
    be provided uniquely for each ifo. The dictionary key is set to H1 and the
    value to H1:CHANNEL_NAME for this example.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        # Again this is modified from the standard argparse 'append' action
        err_msg = "Issue with option: %s \n" %(self.dest,)
        err_msg += "Received value: %s \n" %(' '.join(values),)
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, {})
        items = getattr(namespace, self.dest)
        items = copy.copy(items)
        for value in values:
            value_split = value.split(':')
            if len(value_split) == 2:
                # "Normal" case, all ifos supplied independently as "H1:VALUE"
                if value_split[0] in items:
                    err_msg += "Multiple values supplied for ifo %s.\n" \
                               %(value_split[0],)
                    err_msg += "Already have %s." %(items[value_split[0]])
                    raise ValueError(err_msg)
                else:
                    items[value_split[0]] = value
            elif len(value_split) == 3:
                # This is an unadvertised feature. It is used for cases where I
                # want to pretend H1 data is actually L1 (or similar). So if I
                # supply --channel-name H1:L1:LDAS-STRAIN I can use L1 data and
                # pretend it is H1 internally.
                if value_split[0] in items:
                    err_msg += "Multiple values supplied for ifo %s.\n" \
                               %(value_split[0],)
                    err_msg += "Already have %s." %(items[value_split[0]])
                    raise ValueError(err_msg)
                else:
                    items[value_split[0]] = ':'.join(value_split[1:3])
            else:
                err_msg += "The character ':' is used to deliminate the "
                err_msg += "ifo and the value. It must appear exactly "
                err_msg += "once."
                raise ValueError(err_msg)
        setattr(namespace, self.dest, items)

class MultiDetMultiColonOptionAction(MultiDetOptionAction):
    """A special case of `MultiDetOptionAction` which allows one to use
    arguments containing colons, such as `V1:FOOBAR:1`. The first colon is
    assumed to be the separator between the detector and the argument.
    All subsequent colons are kept as part of the argument. Unlike
    `MultiDetOptionAction`, all arguments must be prefixed by the
    corresponding detector.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        err_msg = ('Issue with option: {}\n'
                   'Received value: {}\n').format(self.dest, ' '.join(values))
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, {})
        items = copy.copy(getattr(namespace, self.dest))
        for value in values:
            if ':' not in value:
                err_msg += ("Each argument must contain at least one ':' "
                            "character")
                raise ValueError(err_msg)
            detector, argument = value.split(':', 1)
            if detector in items:
                err_msg += ('Multiple values supplied for detector {},\n'
                            'already have {}.')
                err_msg = err_msg.format(detector, items[detector])
                raise ValueError(err_msg)
            items[detector] = self.internal_type(argument)
        setattr(namespace, self.dest, items)

class MultiDetOptionAppendAction(MultiDetOptionAction):
    def __call__(self, parser, namespace, values, option_string=None):
        # Again this is modified from the standard argparse 'append' action
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, {})
        items = getattr(namespace, self.dest)
        items = copy.copy(items)
        for value in values:
            value = value.split(':')
            if len(value) == 2:
                # "Normal" case, all ifos supplied independetly as "H1:VALUE"
                if value[0] in items:
                    items[value[0]].append(self.internal_type(value[1]))
                else:
                    items[value[0]] = [self.internal_type(value[1])]
            else:
                err_msg = "Issue with option: %s \n" %(self.dest,)
                err_msg += "Received value: %s \n" %(' '.join(values),)
                err_msg += "The character ':' is used to distinguish the "
                err_msg += "ifo and the value. It must be given exactly once "
                err_msg += "for all entries"
                raise ValueError(err_msg)
        setattr(namespace, self.dest, items)

class DictOptionAction(argparse.Action):
    # Initialise the same as the standard 'append' action
    def __init__(self,
                 option_strings,
                 dest,
                 nargs='+',
                 const=None,
                 default=None,
                 type=None,
                 choices=None,
                 required=False,
                 help=None,
                 metavar=None):
        if type is not None:
            self.internal_type = type
        else:
            self.internal_type = str
        new_default = DictWithDefaultReturn(lambda: default)
        if nargs == 0:
            raise ValueError('nargs for append actions must be > 0; if arg '
                             'strings are not supplying the value to append, '
                             'the append const action may be more appropriate')
        if const is not None and nargs != argparse.OPTIONAL:
            raise ValueError('nargs must be %r to supply const'
                             % argparse.OPTIONAL)
        super(DictOptionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=nargs,
            const=const,
            default=new_default,
            type=str,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar)

    def __call__(self, parser, namespace, values, option_string=None):
        # Again this is modified from the standard argparse 'append' action
        err_msg = "Issue with option: %s \n" %(self.dest,)
        err_msg += "Received value: %s \n" %(' '.join(values),)
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, {})
        items = getattr(namespace, self.dest)
        items = copy.copy(items)
        for value in values:
            if values == ['{}']:
                break
            value = value.split(':')
            if len(value) == 2:
                # "Normal" case, all extra arguments supplied independently
                # as "param:VALUE"
                items[value[0]] = self.internal_type(value[1])
            else:
                err_msg += "The character ':' is used to distinguish the "
                err_msg += "parameter name and the value. Please do not "
                err_msg += "use it more than or less than once."
                raise ValueError(err_msg)
        setattr(namespace, self.dest, items)

class MultiDetDictOptionAction(DictOptionAction):
    """A special case of `DictOptionAction` which allows one to use
    argument containing the detector (channel) name, such as
    `DETECTOR:PARAM:VALUE`. The first colon is the name of detector,
    the second colon is the name of parameter, the third colon is the value.
    Or similar to `DictOptionAction`, all arguments don't contain the name of
    detector, such as `PARAM:VALUE`, this will assume each detector has same
    values of those parameters.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        # Again this is modified from the standard argparse 'append' action
        err_msg = ('Issue with option: {}\n'
                   'Received value: {}\n').format(self.dest, ' '.join(values))
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, {})
        items = copy.copy(getattr(namespace, self.dest))
        detector_args = {}
        for value in values:
            if values == ['{}']:
                break
            if value.count(':') == 2:
                detector, param_value = value.split(':', 1)
                param, val = param_value.split(':')
                if detector not in detector_args:
                    detector_args[detector] = {param: self.internal_type(val)}
                if param in detector_args[detector]:
                    err_msg += ("Multiple values supplied for the same "
                                "parameter {} under detector {},\n"
                                "already have {}.")
                    err_msg = err_msg.format(param, detector,
                                             detector_args[detector][param])
                else:
                    detector_args[detector][param] = self.internal_type(val)
            elif value.count(':') == 1:
                param, val = value.split(':')
                for detector in getattr(namespace, 'instruments'):
                    if detector not in detector_args:
                        detector_args[detector] = \
                            {param: self.internal_type(val)}
                    if param in detector_args[detector]:
                        err_msg += ("Multiple values supplied for the same "
                                    "parameter {} under detector {},\n"
                                    "already have {}.")
                        err_msg = err_msg.format(
                                    param, detector,
                                    detector_args[detector][param])
                    else:
                        detector_args[detector][param] = \
                                    self.internal_type(val)
            else:
                err_msg += ("Use format `DETECTOR:PARAM:VALUE` for each "
                            "detector, or use `PARAM:VALUE` for all.")
                raise ValueError(err_msg)
        items = detector_args
        setattr(namespace, self.dest, items)

def required_opts(opt, parser, opt_list, required_by=None):
    """Check that all the opts are defined

    Parameters
    ----------
    opt : object
        Result of option parsing
    parser : object
        OptionParser instance.
    opt_list : list of strings
    required_by : string, optional
        the option that requires these options (if applicable)
    """
    for name in opt_list:
        attr = name[2:].replace('-', '_')
        if not hasattr(opt, attr) or (getattr(opt, attr) is None):
            err_str = "%s is missing " % name
            if required_by is not None:
                err_str += ", required by %s" % required_by
            parser.error(err_str)

def required_opts_multi_ifo(opt, parser, ifo, opt_list, required_by=None):
    """Check that all the opts are defined

    Parameters
    ----------
    opt : object
        Result of option parsing
    parser : object
        OptionParser instance.
    ifo : string
    opt_list : list of strings
    required_by : string, optional
        the option that requires these options (if applicable)
    """
    for name in opt_list:
        attr = name[2:].replace('-', '_')
        try:
            if getattr(opt, attr)[ifo] is None:
                raise KeyError
        except KeyError:
            err_str = "%s is missing " % name
            if required_by is not None:
                err_str += ", required by %s" % required_by
            parser.error(err_str)

def ensure_one_opt(opt, parser, opt_list):
    """  Check that one and only one in the opt_list is defined in opt

    Parameters
    ----------
    opt : object
        Result of option parsing
    parser : object
        OptionParser instance.
    opt_list : list of strings
    """

    the_one = None
    for name in opt_list:
        attr = name[2:].replace('-', '_')
        if hasattr(opt, attr) and (getattr(opt, attr) is not None):
            if the_one is None:
                the_one = name
            else:
                parser.error("%s and %s are mutually exculsive" \
                              % (the_one, name))

    if the_one is None:
        parser.error("you must supply one of the following %s" \
                      % (', '.join(opt_list)))

def ensure_one_opt_multi_ifo(opt, parser, ifo, opt_list):
    """  Check that one and only one in the opt_list is defined in opt

    Parameters
    ----------
    opt : object
        Result of option parsing
    parser : object
        OptionParser instance.
    opt_list : list of strings
    """

    the_one = None
    for name in opt_list:
        attr = name[2:].replace('-', '_')
        try:
            if getattr(opt, attr)[ifo] is None:
                raise KeyError
        except KeyError:
            pass
        else:
            if the_one is None:
                the_one = name
            else:
                parser.error("%s and %s are mutually exculsive" \
                              % (the_one, name))

    if the_one is None:
        parser.error("you must supply one of the following %s" \
                      % (', '.join(opt_list)))

def copy_opts_for_single_ifo(opt, ifo):
    """
    Takes the namespace object (opt) from the multi-detector interface and
    returns a namespace object for a single ifo that can be used with
    functions expecting output from the single-detector interface.
    """
    opt = copy.deepcopy(opt)
    for arg, val in vars(opt).items():
        if isinstance(val, DictWithDefaultReturn) or \
           (isinstance(val, dict) and ifo in val):
            setattr(opt, arg, getattr(opt, arg)[ifo])
    return opt

def convert_to_process_params_dict(opt):
    """
    Takes the namespace object (opt) from the multi-detector interface and
    returns a dictionary of command line options that will be handled correctly
    by the register_to_process_params ligolw function.
    """
    opt = copy.deepcopy(opt)
    for arg, val in vars(opt).items():
        if isinstance(val, DictWithDefaultReturn):
            new_val = []
            for key in val.keys():
                if isinstance(val[key], list):
                    for item in val[key]:
                        if item is not None:
                            new_val.append(':'.join([key, str(item)]))
                else:
                    if val[key] is not None:
                        new_val.append(':'.join([key, str(val[key])]))
            setattr(opt, arg, new_val)
    return vars(opt)

def _positive_type(s, dtype=None):
    """
    Ensure argument is positive and convert type to dtype

    This is for the functions below to wrap to avoid code duplication.
    """
    assert dtype is not None
    err_msg = f"Input must be a positive {dtype}, not {s}"
    try:
        value = dtype(s)
    except ValueError:
        raise argparse.ArgumentTypeError(err_msg)
    if value <= 0:
        raise argparse.ArgumentTypeError(err_msg)
    return value

def _nonnegative_type(s, dtype=None):
    """
    Ensure argument is positive or zero and convert type to dtype

    This is for the functions below to wrap to avoid code duplication.
    """
    assert dtype is not None
    err_msg = f"Input must be either a positive or zero {dtype}, not {s}"
    try:
        value = dtype(s)
    except ValueError:
        raise argparse.ArgumentTypeError(err_msg)
    if value < 0:
        raise argparse.ArgumentTypeError(err_msg)
    return value

def positive_float(s):
    """
    Ensure argument is a positive real number and return it as float.

    To be used as type in argparse arguments.
    """
    return _positive_type(s, dtype=float)

def nonnegative_float(s):
    """
    Ensure argument is a positive real number or zero and return it as float.

    To be used as type in argparse arguments.
    """
    return _nonnegative_type(s, dtype=float)

def positive_int(s):
    """
    Ensure argument is a positive integer and return it as int.

    To be used as type in argparse arguments.
    """
    return _positive_type(s, dtype=int)

def nonnegative_int(s):
    """
    Ensure argument is a positive integer or zero and return it as int.

    To be used as type in argparse arguments.
    """
    return _nonnegative_type(s, dtype=int)

def angle_as_radians(s):
    """
    Interpret argument as a string defining an angle, which will be converted
    to radians and returned as float. The format can be either "<value><unit>"
    (e.g. 12deg, 1rad), "<value> <unit>" (e.g. 12 deg, 1 rad) or just
    "<value>", in which case the unit will be assumed to be radians.

    Note that the format "<value><unit>", with a negative value and no space,
    is not parsed correctly by argparse; for more information, see
    https://stackoverflow.com/questions/16174992/cant-get-argparse-to-read-quoted-string-with-dashes-in-it

    Note: when writing angles in workflow configuration files as options to be
    passed to executables that rely on this function and require angles in their
    command line, the format "<value> <unit>", with the quotation marks
    included, is required due to how Pegasus renders options in .sh files.

    To be used as type in argparse arguments.
    """
    # if `s` converts to a float then there is no unit, so assume radians
    try:
        value = float(s)
        warnings.warn(
            f'Angle units not specified for {value}, assuming radians'
        )
        return value
    except:
        pass
    # looks like we have units, so do some parsing
    rematch = re.match('([0-9.e+-]+) *(deg|rad)', s)
    value = float(rematch.group(1))
    unit = rematch.group(2)
    if unit == 'deg':
        return math.radians(value)
    if unit == 'rad':
        return value
    raise argparse.ArgumentTypeError(f'Unknown unit {unit}')
