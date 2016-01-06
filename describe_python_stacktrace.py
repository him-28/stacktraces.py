#!/usr/bin/env python

# Copyright 2015 Jeff Trawick, http://emptyhammock.com/
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

import sys

from stacktraces.py_shortcuts import describe_lines


def main():
    if len(sys.argv) != 1:
        print >> sys.stderr, 'Usage: %s' % sys.argv[0]
        sys.exit(1)

    traceback_lines = sys.stdin.readlines()
    print(describe_lines(traceback_lines))

if __name__ == '__main__':
    main()