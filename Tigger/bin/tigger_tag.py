#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# % $Id$
#
#
# Copyright (C) 2002-2011
# The MeqTree Foundation &
# ASTRON (Netherlands Foundation for Research in Astronomy)
# P.O.Box 2, 7990 AA Dwingeloo, The Netherlands
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>,
# or write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import fnmatch
import math
import re
import sys

import os.path

DEG = math.pi / 180
ARCSEC = DEG / 3600

NATIVE = "Tigger"


def transfer_tags(fromlsm, lsm, output, tags, tolerance, tigger):
    """Transfers tags from a reference LSM to the given LSM. That is, for every tag
    in the given list, finds all sources with those tags in 'fromlsm', then applies
    these tags to all nearby sources in 'lsm' (within a radius of 'tolerance').
    Saves the result to an LSM file given by 'output'.
    """
    # now, set dE tags on sources
    tagset = frozenset(tags.split())
    print("Transferring tags %s from %s to %s (%.2f\" tolerance)" % (",".join(tagset), fromlsm, lsm, tolerance))

    refmodel = tigger.load(fromlsm)
    model = tigger.load(lsm)
    # for each dE-tagged source in the reference model, find all nearby sources
    # in our LSM, and tag them
    for src0 in refmodel.getSourceSubset(",".join(["=" + x for x in tagset])):
        for src in model.getSourcesNear(src0.pos.ra, src0.pos.dec, tolerance=tolerance * ARCSEC):
            for tag in tagset:
                tagval = src0.getTag(tag, None)
                if tagval is not None:
                    if src.getTag(tag, None) != tagval:
                        src.setTag(tag, tagval)
                        print("setting tag %s=%s on source %s (from reference source %s)" % (
                        tag, tagval, src.name, src0.name))
    model.save(output)


def main():
    import Kittens.utils

    _verbosity = Kittens.utils.verbosity(name="convert-model")
    dprint = _verbosity.dprint
    dprintf = _verbosity.dprintf

    # find Tigger
    try:
        import Tigger
    except ImportError:
        dirname = os.path.dirname(os.path.realpath(__file__))
        # go up the directory tree looking for directory "Tigger"
        while len(dirname) > 1:
            if os.path.basename(dirname) == "Tigger":
                break
            dirname = os.path.dirname(dirname)
        else:
            print("Unable to locate the Tigger directory, it is not a parent of %s. Please check your installation and/or PYTHONPATH." % os.path.realpath(
                __file__))
            sys.exit(1)
        sys.path.append(os.path.dirname(dirname))
        try:
            import Tigger
        except:
            print("Unable to import the Tigger package from %s. Please check your installation and PYTHONPATH." % dirname)
            sys.exit(1)

    Tigger.nuke_matplotlib()  # don't let the door hit you in the ass, sucka

    # setup some standard command-line option parsing
    #
    from optparse import OptionParser

    parser = OptionParser(
        usage="""%prog: sky_model [NAME or SELTAG<>SELVAL] [TAG=[TYPE:]VALUE or +TAG or !TAG or /TAG ...]""",
        description=
        """Sets or changes tags of selected sources in the sky model.
        Use NAME (with shell-style wildcards allowed) to select sources by name, or 
        =SELTAG to select sources having the specified (non-zero) tag, or SELTAG<>SELVAL to
        select sources by comparing a tag to a value, where '<>'  represents a comparison
        operator, and can be one of == (or =),!=,<=,<,>,>= (or the FORTRAN-style
        operators .eq.,.ne.,.le.,.lt.,.gt.,.ge.). SELVAL may also be followed by one of the characters 
        'd', 'm' or 's', in which case it will be converted from degrees,
        minutes or seconds into radians. This is useful for selections such as "r<5d".
        Then, with a subset of sources selected, use TAG=TYPE:VALUE (where TYPE is one of: bool, int, float, str, complex)
        to set a tag on the selected sources to a value of a specific type, or TAG=VALUE to determine type
        automatically, or +TAG to set a bool True tag, !TAG to set a False tag, and /TAG to remove a tag."""
        )

    parser.add_option("-l", "--list", action="store_true",
                      help="Simply lists selected sources, does not apply any tags.")
    parser.add_option("-o", "--output", metavar="FILENAME", type="string",
                      help="Saves changes to different output model. Default is to save in place.")
    parser.add_option("-f", "--force", action="store_true",
                      help="Saves changes to model without prompting. Default is to prompt.")
    parser.add_option("-t", "--transfer-tags", dest="transfer_tags", type="string", metavar="FROM_LSM:TOL",
                      help="""Transfers tags from a reference LSM (FROM_LSM) to the given LSM (sky_model). 
That is, for every tag in the given list, finds all sources with those tags in the reference LSM, 
then applies these tags to all nearby sources in LSM  (within a radius of 'tolerance' [ARCSEC]). 
Saves the result to an LSM file given by -o/--output.
""")
    parser.add_option("-d", "--debug", dest="verbose", type="string", action="append", metavar="Context=Level",
                      help="(for debugging Python code) sets verbosity level of the named Python context. May be used multiple times.")

    parser.set_defaults()

    (options, rem_args) = parser.parse_args()

    # get filenames
    if len(rem_args) < 2:
        parser.error("Incorrect number of arguments. Use -h for help.")

    skymodel = rem_args[0]
    # load the model
    model = Tigger.load(skymodel)
    if not model.sources:
        print("Input model %s contains no sources" % skymodel)
        sys.exit(0)
    print("Input model contains %d sources" % len(model.sources))

    if options.transfer_tags:
        fromlsm, tolerance = options.transfer_tags.split(":")
        tags = " ".join(rem_args[1:])
        transfer_tags(fromlsm, skymodel, options.output, tags, float(tolerance), Tigger)
        sys.exit(0)

    # comparison predicates for the SELTAG<>SELVAL option
    select_predicates = {
        '==': lambda x, y: x == y,
        '!=': lambda x, y: x != y,
        '>=': lambda x, y: x >= y,
        '<=': lambda x, y: x <= y,
        '>': lambda x, y: x > y,
        '<': lambda x, y: x < y,
        '.eq.': lambda x, y: x == y,
        '.ne.': lambda x, y: x != y,
        '.ge.': lambda x, y: x >= y,
        '.le.': lambda x, y: x <= y,
        '.gt.': lambda x, y: x > y,
        '.lt.': lambda x, y: x < y
    }
    # units for same
    select_units = dict(d=DEG, m=DEG / 60, s=DEG / 3600)

    # This is where we accumulate the result of selection arguments, until we hit the first tagging argument.
    # Initially None, meaning no explicit selection
    global selected_ids
    selected_ids = None

    # This is where we put the selection when we hit the first tagging argument.
    global selection
    selection = None

    # this is set to true when the selection is listed
    global listed
    # set to true when the model is modified
    modified = False


    def apply_selection(sel, selstr):
        global selection
        global selected_ids
        global listed
        listed = False
        """Helper function: applies selection argument"""
        # if selection is not None, then we've already selected and tagged something, so we need
        # to reset the selection to empty and start again. If selected_ids is None, this is the first selection
        if selection is not None or selected_ids is None:
            print("Selecting sources:")
            selected_ids = set()
            selection = None
        # add to current selection
        selected_ids.update(list(map(id, sel)))
        # print result
        if not len(sel):
            print('  %-16s: no sources selected' % selstr)
        elif len(sel) == 1:
            print('  %-16s: one source selected (%s)' % (selstr, sel[0].name))
        elif len(sel) <= 5:
            print('  %-16s: %d sources selected (%s)' % (selstr, len(sel), " ".join([src.name for src in sel])))
        else:
            print('  %-16s: %d sources selected' % (selstr, len(sel)))


    def retrieve_selection():
        global selection
        global selected_ids
        """Helper function: retrieves current selection in preparation for tagging"""
        # if selection is None, then we need to set it up based on selected_ids
        if selection is None:
            # no explicit selection: use entire model
            if selected_ids is None:
                selection = model.sources
                print("No explicit selection, using all sources.")
            # else use selected set
            else:
                selection = [src for src in model.sources if id(src) in selected_ids]
                print("Using %d selected sources:" % len(selection))
        if options.list:
            print("Sources: %s" % (" ".join([x.name for x in selection])))
            global listed
            listed = True
        return selection


    def getTagValue(src, tag):
        """Helper function: looks for the given tag in the source, or in its sub-objects"""
        for obj in src, src.pos, src.flux, getattr(src, 'shape', None), getattr(src, 'spectrum', None):
            if obj is not None and hasattr(obj, tag):
                return getattr(obj, tag)
        return None


    def lookupObject(src, tagname):
        """helper function to look into sub-objects of a Source object.
        Given src and "a", returns src,"a"
        Given src and "a.b", returns src.a and "b"
        """
        tags = tagname.split(".")
        for subobj in tags[:-1]:
            src = getattr(src, subobj, None)
            if src is None:
                print("Can't resolve attribute %s for source %s" % (tagname, src.name))
                sys.exit(1)
        return src, tags[-1]


    # loop over all arguments
    for arg in rem_args[1:]:
        # Match either the SELTAG<>SELVAL, or the TAG=[TYPE:]VALUE, or the [+!/]TAG forms
        # If none match, assume the NAME form
        mselcomp = re.match("(?i)^([^=<>!.]+)(%s)([^dms]+)([dms])?" % "|".join(
            [key.replace('.', '\.') for key in list(select_predicates.keys())]), arg)
        mseltag = re.match("=(.+)$", arg)
        mset = re.match("^(.+)=((bool|int|str|float|complex):)?(.+)$", arg)
        msetbool = re.match("^([+!/])(.+)$", arg)

        # SELTAG<>SELVAL selection
        if mselcomp:
            seltag, oper, selval, unit = mselcomp.groups()
            try:
                selval = float(selval) * select_units.get(unit, 1.)
            except:
                parser.error("Malformed selection string '%s': right-hand side is not a number." % arg)
            predicate = select_predicates[oper.lower()]
            # get tag value
            srctag = [(src, getTagValue(src, seltag)) for src in model.sources]
            apply_selection([src for src, tag in srctag if tag is not None and predicate(tag, selval)], arg)
        elif mseltag:
            seltag = mseltag.groups()[0]
            apply_selection([src for src in model.sources if getTagValue(src, seltag)], arg)
        elif not mseltag and not mselcomp and not mset and not msetbool:
            apply_selection([src for src in model.sources if fnmatch.fnmatch(src.name, arg)], arg)
        elif mset:
            sources = retrieve_selection()
            if options.list:
                print("--list in effect, ignoring tagging commands")
                continue
            tagname, typespec, typename, value = mset.groups()
            # if type is specified, use it to explicitly convert the value
            # first bool: allow True/False/T/F
            if typename == "bool":
                val = value.lower()
                if val == "true" or val == "t":
                    newval = True
                elif val == "false" or val == "f":
                    newval = False
                else:
                    try:
                        newval = bool(int(value))
                    except:
                        print("Can't parse \"%s\" as a value of type bool" % value)
                        sys.exit(2)
            # else some other type is specified -- use it to convert the value
            elif typename:
                try:
                    newval = getattr(globals()["__builtin__"], typename)(value)
                except:
                    print("Can't parse \"%s\" as a value of type %s" % (value, typename))
                    sys.exit(2)
            # else auto-convert
            else:
                newval = None
                for tp in int, float, complex, str:
                    try:
                        newval = tp(value)
                        break
                    except:
                        pass
            # ok, value determined
            if type(newval) is str:
                value = '"%s"' % value
            if sources:
                print("  setting tag %s=%s (type '%s')" % (tagname, value, type(newval).__name__))
                for src in sources:
                    obj, tag = lookupObject(src, tagname)
                    obj.setAttribute(tag, newval)
                modified = True
            else:
                print("No sources selected, ignoring tagging commands")
        elif msetbool:
            sources = retrieve_selection()
            if options.list:
                print("--list in effect, ignoring tagging commands")
                continue
            if sources:
                op, tagname = msetbool.groups()
                if op == "+":
                    print("  setting tag %s=True" % tagname)
                    method = 'setAttribute'
                    args = (tagname, True)
                elif op == "!":
                    print("  setting tag %s=False" % tagname)
                    method = 'setAttribute'
                    args = (tagname, False)
                elif op == "/":
                    print("  removing tag %s" % tagname)
                    method = 'removeAttribute'
                    args = (tagname,)
                for src in sources:
                    obj, tag = lookupObject(src, tagname)
                    getattr(obj, method)(*args)
                modified = True
            else:
                print("No sources selected, ignoring tagging commands")

    if options.list:
        if not listed:
            retrieve_selection()

    if not modified:
        print("Model was not modified")
        sys.exit(0)

    # prompt
    if not options.force:
        try:
            input("Press ENTER to save model or Ctrl+C to cancel: ")
        except:
            print("Cancelling")
            sys.exit(1)

    # save output
    if options.output:
        model.save(options.output)
        print("Saved updated model to %s" % options.output)
    else:
        model.save(skymodel)
        print("Saved updated model")
