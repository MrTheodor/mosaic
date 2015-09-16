# follow.py
#
# Follow a file like tail -f.

import time

if __name__ == '__main__':
    logfile = open("./log","rt")
    logfile.seek(0,0)
    while True:
        line = logfile.readline()
        if not line:
            time.sleep(0.1)
            continue
        print line