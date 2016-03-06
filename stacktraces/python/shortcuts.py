from __future__ import print_function

from collections import defaultdict
import json
import re

from six import text_type

from stacktraces import process_model, thread_analyzer
from stacktraces.python import stacktrace


def get_process_from_traceback(traceback_lines, name=None):
    p = process_model.Process(0)
    ptb = stacktrace.PythonTraceback(
        proc=p, lines=traceback_lines, name=name,
    )
    ptb.parse()
    # thread_analyzer.cleanup(p, my_cleanups)
    # thread_analyzer.annotate(p, my_annotations)
    p.group()  # only one thread, but this allows str(p) to work
    return p


def describe_lines(traceback_lines):
    return text_type(get_process_from_traceback(traceback_lines))

LOGLVL_RE = r'(CRITICAL|ERROR|WARNING|INFO|DEBUG)'
TRACE_MSG_RE_1 = re.compile(r'^\[([^]]+)\] ' + LOGLVL_RE + ' \[[^]]+\] (.*)\n?$')
TRACE_MSG_RE_2 = re.compile(r'^(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d).*' + LOGLVL_RE + ' +(.*)\n?$')
TRACE_MSG_RE_3 = re.compile(r'^(\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d) .*\[' + LOGLVL_RE + '\] +(.*)\n?')
TRACE_MSG_RE_4 = re.compile(r'^.*\[([A-Z][a-z][a-z] [A-Z][a-z][a-z] \d\d \d\d:\d\d:\d\d \d\d\d\d)\] +(.*)\n?')
TRACE_MSG_RE_DEFAULT = re.compile(r'^\[[^]]+\] *(.*)\n?$')

TRACE_MSG_RES = [
    (TRACE_MSG_RE_1, 1, 3,),
    (TRACE_MSG_RE_2, 1, 3,),
    (TRACE_MSG_RE_3, 1, 3,),
    (TRACE_MSG_RE_4, 1, 2),
    (TRACE_MSG_RE_DEFAULT, None, 1)
]


def parse_trace_msg(msg):
    for regex, timestamp_index, msg_index in TRACE_MSG_RES:
        m = regex.match(msg)
        if m:
            if timestamp_index is not None:
                timestamp = m.group(timestamp_index)
            else:
                timestamp = None
            if msg_index is not None:
                msg = m.group(msg_index)
            else:
                msg = None
            return timestamp, msg
    return None, None


def handle_traceback(traceback_lines, msg, tracelvl, cleanups, annotations):
    # We just have a traceback from an individual thread, so skip:
    # . ProcessGroup representation
    # . Process.group(), which finds threads in a process with same backtrace

    if msg:
        timestamp, _ = parse_trace_msg(msg.line)
    else:
        timestamp = None
    # if not timestamp:
    #     raise ValueError('Cannot parse log message "%s"' % msg)

    # Ignore error message in the related log message for now; it seems to be
    # always duplicated within the traceback output
    p = process_model.Process(0)
    ptb = stacktrace.PythonTraceback(
        proc=p, lines=traceback_lines, timestamp=timestamp,
    )
    ptb.parse()
    thread_analyzer.cleanup(p, cleanups)
    thread_analyzer.annotate(p, annotations)
    p.group()  # only one thread, but this allows str(p) to work
    if tracelvl > 1:
        print('-------------')
        print(traceback_lines)
    return p, traceback_lines


class Line(object):
    def __init__(self, line):
        self.line = line
        self.is_start_of_traceback = line.startswith('Traceback ')
        self.is_log_msg = False
        if not self.is_start_of_traceback:
            timestamp, msg = parse_trace_msg(line)
            if timestamp or msg:
                self.is_log_msg = True

    def __str__(self):
        return '%s%s%s' % (
            'TB ' if self.is_start_of_traceback else '',
            'LG ' if self.is_log_msg else '',
            self.line,
        )


class ParseState(object):
    def __init__(self):
        self.in_traceback = False
        self.traceback_lines = []
        self.traceback_log_msg = None

    def __str__(self):
        fields = []
        if self.in_traceback:
            fields.append('IN-TB')
            fields.append('%s..' % self.traceback_lines[0])
            if self.traceback_log_msg:
                fields.append(self.traceback_log_msg.line)
        return ' '.join(fields)


def read_log(tracelvl, logfile, cleanups=(), annotations=()):
    prev_log_msg = None
    s = ParseState()

    while True:
        l = logfile.readline()
        if l == '':
            break
        l = Line(l)
        if l.is_start_of_traceback:
            if s.in_traceback:
                yield handle_traceback(s.traceback_lines, s.traceback_log_msg, tracelvl, cleanups, annotations)
                s = ParseState()
            s.in_traceback = True
            s.traceback_log_msg = prev_log_msg
        elif l.is_log_msg and s.traceback_lines:
            yield handle_traceback(s.traceback_lines, s.traceback_log_msg, tracelvl, cleanups, annotations)
            s = ParseState()
        if s.in_traceback and not (l.line.startswith('[') or l.line in ('', '\n')):
            s.traceback_lines.append(l.line)
        if l.is_log_msg:
            prev_log_msg = l
    if s.in_traceback:
        yield handle_traceback(s.traceback_lines, s.traceback_log_msg, tracelvl, cleanups, annotations)
        # s = ParseState()


def _output_process(
        output_format,
        include_duplicates, include_raw, messages, stacktraces, need_delim,
        process, traceback_lines, outfile
):
    thread = process.threads[0]
    st = ', '.join([f.fn for f in thread.frames])

    if not include_duplicates:
        if thread.failure_text:
            messages[thread.failure_text] += 1
        if thread.error_msg:
            messages[thread.error_msg] += 1
        stacktraces[st] += 1
        if stacktraces[st] > 1:
            return need_delim

    if output_format == 'text':
        if thread.error_msg:
            print(thread.error_msg, file=outfile)
        if thread.failure_text:
            print(thread.failure_text, file=outfile)
        print(st, file=outfile)
        if include_raw:
            print(''.join(traceback_lines), file=outfile)
        print(file=outfile)
    else:
        if need_delim:
            print(',', file=outfile)
        if include_raw:
            to_serialize = {
                'wrapped': process.description(wrapped=True),
                'raw': ''.join(traceback_lines)
            }
        else:
            to_serialize = process.description(wrapped=True)
        print(json.dumps(to_serialize), file=outfile)
        need_delim = True

    return need_delim


def process_log_file(
        log_file, outfile,
        output_format='text', include_duplicates=False, include_raw=False
):
    need_delim = False

    if output_format == 'json':
        print('[', file=outfile)

    message_counts = defaultdict(int)
    stacktrace_counts = defaultdict(int)

    for p, traceback_lines in read_log(tracelvl=1, logfile=log_file):
        need_delim = _output_process(
            output_format, include_duplicates, include_raw, message_counts,
            stacktrace_counts, need_delim, p, traceback_lines, outfile
        )
    if output_format == 'json':
        print(']', file=outfile)

    return message_counts, stacktrace_counts
