import hashlib
import os
import glob
import pathlib
from pathlib import Path
from ctypes.wintypes import MAX_PATH

from tkinter import filedialog, messagebox
from tkinter import Tk, Button, Label, font

from functools import partial
from unicodedata import normalize

version = "0.6"

error_file = "ACOUA_md5_errors.txt"


def log_message(message):
    f_err = open(error_file, "a")
    f_err.write(message + '\n')
    f_err.close()


def md5Checksum(filePath):
    # blocksize = 8192
    # switch to 1MB blocks to improve performance
    blocksize = 2**20
    with open(filePath, 'rb') as fh:
        m = hashlib.md5()
        while True:
            data = fh.read(blocksize)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


def runchecksum(tkroot, width_chars):
    # Clear all existing text messages
    for label in tkroot.winfo_children():
        if type(label) is Label:
            label.destroy()
    

    error_message = f"There were errors or warnings during processing:\ncheck {error_file} for information."
    error_file_header = "This is the acouachecksum log for errors and warnings. Do not archive.\n"

    d_title = "Select your ingestion folder"
    choosedir = filedialog.askdirectory(initialdir=Path.home(), title=d_title)
    if choosedir == '' or not os.path.exists(choosedir):
        return
    os.chdir(choosedir)

    # delete existing logfile unless it doesn't exist
    try:
        os.remove(error_file)
    except OSError:
        pass

    # Normalize base folder to the OS's convention, disregard askdirectory()'s weirdness
    choosedir = os.getcwd()

    choosedir_display = ''
    line_length = 0
    for fs_level in choosedir.split(os.sep):
        if len(fs_level) > width_chars:
            fs_level = fs_level[0:width_chars-6] + '[...]'

        if line_length + len(fs_level) < width_chars:
            choosedir_display += fs_level + os.sep
            line_length += len(fs_level) + 1
        else:
            choosedir_display += '\n'
            choosedir_display += fs_level + os.sep
            line_length = len(fs_level) + 1

    path_info = Label(tkroot, text=f'Processing:\n{choosedir_display}')
    path_info.pack()
    tkroot.update()

    # Create logfile for potential warnings and errors
    log_message(error_file_header)

    all_files = pathlib.Path(choosedir).rglob('**/*')
    files = []
    # Create Tk label for progress information: counting files
    progress_update_frequency = 10
    progress_info = Label(tkroot, text=f'Listing: {len(files)} files')
    progress_info.pack()
    tkroot.update()
    for ls in all_files:
        # print(os.path.join(str(ls.parents[0]), ls.name))
        if len(os.path.join(str(ls.parents[0]), ls.name)) > MAX_PATH:
            log_message(f"WARNING > {MAX_PATH} chars for path + file name: {os.path.join(str(ls.parents[0]), ls.name)}")
        filename = os.path.join(str(ls.parents[0]).replace(choosedir, '.'), ls.name)
        if not filename.endswith(os.sep + '.DS_Store') \
                and not filename.endswith(os.sep + 'Thumbs.db') \
                and not filename.startswith(os.path.join(choosedir, 'ACOUA_md5.md5')) \
                and not filename.startswith(os.path.join('.', 'ACOUA_md5.md5')) \
                and not os.path.isdir(filename):
            #filename = os.path.join([str(ls.parents[0]).replace(choosedir,'.'), ls.name])
            if filename.startswith('/'):
                files.append(filename[1:])
            else:
                files.append(filename)

        if len(files) % progress_update_frequency == 0:
            #print(f'Listing: {len(files)} files')
            progress_info.config(text=f'Listing: {len(files)} files')
            tkroot.update()

    # print('Done listing')
    # the progress information label will now display the actual checksum progress
    # switch to individual file progress frequency: chekcsum is much slower
    progress_update_frequency = 1
    progress = 0
    progress_info .config(text=f'Checksum progress: {progress}/{len(files)}')
    tkroot.update()

    f = open("ACOUA_md5.md5", "wb")
    
    for element in files:
        progress += 1
        try:
            md5 = md5Checksum(element)
            # filenames must be encoded as UTF-8, or they might not match what Libsafe sees on the filesystem
            # also: NFC normalization for proper (composed) representation of accented characters
            f.write(normalize('NFC',f'{md5} {element.replace(choosedir,".")}\n').encode("UTF-8"))
        except Exception as e:
            trace = str(e)
            log_message(trace)
        if progress % progress_update_frequency == 0:
            #print(f'Progress: {progress}/{len(files)}')
            progress_info.config(text=f'Progress: {progress}/{len(files)}')
            tkroot.update()

    f.close()
    progress_info.config(text=f'Progress: {progress}/{len(files)}')
    tkroot.update()

    f_err = open(error_file, "r")
    error_content = f_err.read()
    f_err.close()
    
    if error_content.replace('\r', '').replace('\n', '') == error_file_header.replace('\r', '').replace('\n', ''):
        os.remove(error_file)
    else:
        error_info = Label(tkroot, text=error_message)
        error_info.pack()

    done_info = Label(tkroot, text=f'Done: ACOUA_md5.md5 has been created')
    done_info.pack()


root = Tk()
current_font = font.nametofont("TkDefaultFont")
root.wm_title("ACOUA CheckSum v" + version)
width = 400
width_chars = int(1.7*width / current_font.actual()['size'])
root.geometry(f'{width}x250+1000+300')

button_label = 'Select a directory and run checksum'
Button(root, text=button_label, command=partial(runchecksum, root, width_chars)).pack()
root.mainloop()
