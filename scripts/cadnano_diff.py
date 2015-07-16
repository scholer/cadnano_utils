

from __future__ import print_function, absolute_import
import os
import argparse
import yaml
import json
import glob
from itertools import zip_longest
import logging
logger = logging.getLogger(__name__)


def parse_args(argv=None):
    """
    Parse command line arguments.
    """

    parser = argparse.ArgumentParser(description="Show differences between two cadnano files.")
    parser.add_argument("--verbose", "-v", action="count", help="Increase verbosity.")
    parser.add_argument("--testing", action="store_true", help="Run app in simple test mode.")
    parser.add_argument("--loglevel", default=logging.INFO, help="Set logging output threshold level.")
    parser.add_argument("--logformat",
                        default="%(asctime)s %(levelname)-5s %(name)12s:%(lineno)-4s%(funcName)16s() %(message)s",
                        help="Set logging output format.")

    parser.add_argument("--config", "-c",
                        help="Instead of providing a bunch of command line arguments at the command line, "
                        "you can read arguments from a dictionary stored as a yaml file).")


    parser.add_argument("files", nargs="+", help="File to diff.")


    return parser, parser.parse_args(argv)




def process_args(argns):
    """
    Process command line args and return a dict with args.

    If argns is given, this is used for processing.
    If argns is not given (or None), parse_args() is called
    in order to obtain a Namespace for the command line arguments.

    Will expand the entry "basedirs" using glob matching, and print a
    warning if a pattern does not match any files at all.

    If argns (given or obtained) contains a "config" attribute,
    this is interpreted as being the filename of a config file (in yaml format),
    which is loaded and merged with the args.

    Returns a dict.
    """
    args = argns.__dict__.copy()

    # Load config with parameters:
    if args.get("config"):
        with open(args["config"]) as fp:
            cfg = yaml.load(fp)
        args.update(cfg)

    if args.get("loglevel"):
        try:
            args["loglevel"] = int(args.get("loglevel"))
        except ValueError:
            args["loglevel"] = getattr(logging, args["loglevel"])

    # On Windows we have to expand glob patterns manually:
    # Also warn user if a pattern does not match any files
    for argname in ("files", ):
        if args.get(argname):
            file_pattern_matches = [(pattern, glob.glob(os.path.expanduser(pattern))) for pattern in args[argname]]
            for pattern in (pattern for pattern, res in file_pattern_matches if len(res) == 0):
                print("WARNING: File/pattern '%s' does not match any files." % pattern)
            args[argname] = [fname for pattern, res in file_pattern_matches for fname in res]

    return args

def init_logging(args):
    """ Initialize logging based on args parameters. """
    default_fmt = "%(asctime)s %(levelname)-5s %(name)12s:%(lineno)-4s%(funcName)16s() %(message)s"
    logging.basicConfig(level=args.get("loglevel", 30),
                        format=args.get("logformat", default_fmt))


def json_file_diff(filepath1, filepath2):
    """ Compare two cadnano json files. """
    with open(filepath1) as file1, open(filepath2) as file2:
        design1 = json.load(file1)
        design2 = json.load(file2)
    # cadnano files are serialized dicts, with keys: vstrands, name
    # vstrands is a list of dicts keys:
    # 'row', 'stapLoop', 'num', 'scafLoop', 'stap_colors', 'scaf', 'stap', 'skip', 'col', 'loop'
    #
    diff_designs(design1, design2)


def list_to_tups(obj):
    """ Convert all lists and dicts in obj to tuples and ensure that obj is hashable. """
    if isinstance(obj, list):
        return tuple(list_to_tups(elem) for elem in obj)
    elif isinstance(obj, list):
        try:
            # See if tuple obj is hashable
            hash(obj)
            return obj
        except TypeError:
            return tuple(list_to_tups(elem) for elem in obj)
    elif isinstance(obj, dict):
        return tuple((k, list_to_tups(v)) for k, v in sorted(obj.items()))
    else:
        hash(obj)   # Assert that the object is hashable
        return obj


def diff_designs(design1, design2):
    """
    Compare two cadnano (v1) objects (after loading from json files).
    """
    if design1['name'] != design2['name']:
        print("New name:", design1['name'], "->", design2['name'])
    if design1['vstrands'] == design2['vstrands']:
        print("The two designs share the exact same vstrands.")
        return
    old_vstrands = design1['vstrands']
    old_vstrands_tups = list_to_tups(old_vstrands)
    old_vstrands_set = set(old_vstrands_tups)
    new_vstrands = design2['vstrands']
    new_vstrands_tups = list_to_tups(new_vstrands)
    new_vstrands_set = set(new_vstrands_tups)
    # set arithmatics: & = intersection = common elements; | = union;
    # s - t = set with elements in s but not in t; s ^ t = new set with elements in either s or t but not both
    vstrands_common = new_vstrands_set & old_vstrands_set
    vstrands_added = new_vstrands_set - old_vstrands_set
    vstrands_removed = old_vstrands_set - new_vstrands_set
    changed_mask = [new != old for new, old in zip_longest(new_vstrands_tups, old_vstrands_tups)]
    # changed_mask[i] is True if old_vstrands[i] is different from new_vstrands[i]
    n_changed = sum(changed_mask)
    if n_changed == 0:
        print("No pair-wise changes in vstrands.")
        return
    # There should be some threshold depending on n_changed.
    # If e.g. a vstrand has been inserted early, do not do pair-wise comparison.
    #for vstrand in old_vstrands_tups:
    print(n_changed, "pair-wise changes in vstrands.")
    print(len(vstrands_added), "vstrands added")
    print(len(vstrands_removed), "vstrands removed")
    print(len(vstrands_common), "vstrands in common (although could be shuffled around)")
    print("Pairwise changes:")
    for i, (new_vs, old_vs) in enumerate(zip_longest(new_vstrands_tups, old_vstrands_tups)):
        if new_vs == old_vs:
            continue
        if old_vs is None or new_vs is None:
            print("extended vstrand", i, ("new" if old_vs is None else "old"), "vstrand added.")
            continue
        if old_vs in vstrands_common:
            old_vstrands_tups.index(new_vstrands_tups[0])
            print("old vstrand", i, "moved to", new_vstrands_tups.index(old_vs), "(but is otherwise identical)")
            continue
        for (oldk, oldv), (newk, newv) in zip(old_vs, new_vs):
            if not oldk == newk:
                print("vstrand %s change in keys '%s' != '%s' - this should not happen!!" % (i, oldk, newk))
                continue
            if newv == oldv:
                continue
            else:
                print("'%s' is changed in vstrand %s (index %s)" % (oldk, old_vs.get('num'), i))









def main(argv=None):
    """ Main driver to parse arguments and start stitching. """
    _, argns = parse_args(argv)
    args = process_args(argns)
    init_logging(args)
    logger.debug("args: %s", args)
    json_file_diff(*args['files'])




if __name__ == '__main__':
    main()
