#!/usr/bin/env python

# Copyright 2012 Jeff Trawick, http://emptyhammock.com/
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from __future__ import print_function

import re
from optparse import OptionParser
import subprocess

from stacktraces import process_model, thread_analyzer
from stacktraces.analyze import httpd
from stacktraces.native import debugger


def add_children(pids):
    cmd = ['ps', '-A', '-o', 'pid,ppid']
    stdout = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]
    for l in stdout.split('\n'):
        m = re.search('(\d+)[ \t]*%s' % pids[0], l)
        if m:
            pids.append(m.group(1))


def main():
    parser = OptionParser()
    parser.add_option("-l", "--debuglog", dest="debuglog", type="string",
                      action="store",
                      help="specify log with debugger output to analyze")
    parser.add_option("-p", "--pid", dest="pid", type="int",
                      action="store",
                      help="specify process id to analyze")
    parser.add_option("-f", "--follow", dest="follow",
                      action="store_true",
                      help="describe child processes too")
    parser.add_option("-e", "--exe", dest="exe", type="string",
                      action="store",
                      help="point to executable for process")
    parser.add_option("-c", "--corefile", dest="corefile", type="string",
                      action="store",
                      help="point to core file to examine")
    parser.add_option("-i", "--infolvl", dest="infolvl", type="int",
                      action="store",
                      help="specify level of information to be displayed")
    parser.add_option("--format", dest="format", type="string",
                      action="store",
                      help="output format -- text (default) or raw")

    (options, args) = parser.parse_args()

    if not options.pid and not options.corefile and not options.debuglog:
        parser.error("Either --pid or --corefile or --debuglog is required.")

    if options.format:
        options.format = options.format.upper()
        if not options.format == 'TEXT' and not options.format == 'RAW':
            parser.error('Invalid value "%s" for --format' % options.format)
    else:
        options.format = 'TEXT'

    mutually_exclusive = (
        ("debuglog", "pid"),
        ("debuglog", "corefile"),
        ("debuglog", "follow"),
        ("pid", "corefile"),
        ("follow", "corefile")
    )

    for opt1, opt2 in mutually_exclusive:
        if getattr(options, opt1) and getattr(options, opt2):
            parser.error("--%s and --%s are mutually exclusive" % (opt1, opt2))

    if options.debuglog:
        debuglog = open(options.debuglog).readlines()
    else:
        debuglog = None

    pids = [options.pid]

    if options.follow:
        add_children(pids)

    group = process_model.ProcessGroup()

    for pid in pids:
        p = process_model.Process(pid)
        group.add_process(p)

        x = debugger.Debugger(proc=p, exe=options.exe, corefile=options.corefile, debuglog=debuglog)
        x.parse()

        thread_analyzer.cleanup(p, httpd.httpd_cleanups)
        thread_analyzer.annotate(p, httpd.httpd_annotations)
        p.group()

    if options.format == 'TEXT':
        print(group.describe(options.infolvl))
    else:
        print(group.description())

if __name__ == '__main__':
    main()
