import hashlib
import os
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import *


def md5Checksum(filePath):
    with open(filePath, 'rb') as fh:
        m = hashlib.md5()
        while True:
            data = fh.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def _path_to_dict(path):
    d = []
    if os.path.exists(path):
        for ls in os.listdir(path):
            if not ls.startswith('.') and not ls.startswith('.DS_Store') and not ls.startswith('ACOUA_md5.md5'):
                ls = Path(os.path.join(path, ls))
                if os.path.isdir(ls):
                    d.append(_path_to_dict(ls))
                else:
                    d.append(os.path.relpath(ls))
        return d


def flatten(l): return flatten(l[0]) + (flatten(l[1:]) if len(l) > 1 else []) if type(l) is list else [l]


def runchecksum():
    choosedir = filedialog.askdirectory(initialdir=Path.home(), title="Select your ingestion folder")
    if choosedir == '' or not os.path.exists(choosedir):
        return
    os.chdir(choosedir)

    files = flatten(_path_to_dict(choosedir))
    f = open("ACOUA_md5.md5", "w")
    for element in files:
        md5 = md5Checksum(element)
        f.write(md5 + " " + "./" + element+"\n")
    f.close()
    messagebox.showinfo(title="Done", message="ACOUA_md5.md5 created")


root = Tk()
root.wm_title("ACOUA CheckSum")
root.geometry('400x250+1000+300')

Button(root, text='Select a directory and run checksum', command=runchecksum).pack()
root.mainloop()
