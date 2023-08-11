import hashlib
import os
import sys
import glob
import pathlib
import shutil
import zipfile
import py7zr
import tarfile
import rarfile
from pathlib import Path
from ctypes.wintypes import MAX_PATH

import tkinter as tk
from tkinter import font, filedialog, ttk

from functools import partial
from unicodedata import normalize

version = "0.8"

error_file = "ACOUA_md5_errors.txt"

# expected path of the ingestion folder... we use the test value, which is a bit longer
libsafe_ingestion_path_prefix = "//nas-app-ma-cifs1.epfl.ch/si_datarepo_inj_test_app/LIBSAFE/ING/ING*******/"
backslash = '\\'

compressed_extensions = ('.zip', '.7z', '.rar', '.tar')
multipart_hint_extensions = ('.z01', '.z001', '.part1.rar')


def remove_archiver():
    selected_checkboxs = listbox.curselection()
    for selected_checkbox in selected_checkboxs[::-1]:
        listbox.delete(selected_checkbox)


def add_archiver(arch_format):
    listbox.insert("end", arch_format)


# A few generic functions to handle divergences between zipfile, py7zr, etc. classes.

def open_archive(ls, extension):
    if isinstance(ls, pathlib.PosixPath):
        archivename = os.path.join(str(ls.parents[0]), ls.name)
    if isinstance(ls, str):
        archivename = ls
    if extension == '.zip':
        return (archivename, zipfile.ZipFile(archivename, mode="r"))
    if extension == '.7z':
        return (archivename, py7zr.SevenZipFile(archivename, mode="r"))
    if extension == '.rar':
        return (archivename, rarfile.RarFile(archivename, mode="r"))
    if extension == '.tar':
        return (archivename, tarfile.TarFile(archivename, mode="r"))


def archive_content(archive):
    if isinstance(archive, zipfile.ZipFile):
        return archive.infolist()
    if isinstance(archive, py7zr.SevenZipFile):
        return archive.list()
    if isinstance(archive, tarfile.TarFile):
        return archive.getmembers()
    if isinstance(archive, rarfile.RarFile):
        return archive.infolist()


def isdir(arch_object):
    if isinstance(arch_object, zipfile.ZipInfo):
        return arch_object.is_dir()
    if isinstance(arch_object, py7zr.FileInfo):
        return arch_object.is_directory
    if isinstance(arch_object, tarfile.TarInfo):
        return arch_object.isdir()
    if isinstance(arch_object, rarfile.RarInfo):
        return arch_object.isdir()


def archive_object_filename(arch_object):
    if isinstance(arch_object, zipfile.ZipInfo):
        return arch_object.filename
    if isinstance(arch_object, py7zr.FileInfo):
        return arch_object.filename
    if isinstance(arch_object, tarfile.TarInfo):
        return arch_object.name
    if isinstance(arch_object, rarfile.RarInfo):
        return arch_object.filename


def log_message(message):
    f_err = open(error_file, "a")
    f_err.write(message + '\n')
    f_err.close()


def is_cp850(s):
    # One way to check whether filenames are encoded as cp850 **sigh** or as utf-8
    try:
        x = s.encode('cp850').decode('utf-8')
        return True
    except:
        return False


def md5Checksum(filePath, ziparchive=None):
    # blocksize = 8192
    # switch to 1MB blocks to improve performance
    blocksize = 2**20
    if ziparchive is None:
        fh = open(filePath, 'rb')
    elif isinstance(ziparchive, py7zr.SevenZipFile):
        # Use the BytesIO part of the response, the filename can be discarded
        ziparchive.reset()
        fname, fh = list(ziparchive.read(filePath).items())[0]
    elif isinstance(ziparchive, tarfile.TarFile):
        tmp_checksum_folder = 'tmp_checksum_folder'
        ziparchive.extract(filePath, path=tmp_checksum_folder)
        fh = open(tmp_checksum_folder + os.sep + filePath, 'rb')
        shutil.rmtree(tmp_checksum_folder)
    else:
        fh = ziparchive.open(filePath, 'r')

    m = hashlib.md5()
    while True:
        data = fh.read(blocksize)
        if not data:
            break
        m.update(data)
    return m.hexdigest()


def runchecksum(tkroot, width_chars, check_zips):
    # Clear all existing text messages
    do_zips = bool(check_zips.get())

    archiver_list = listbox.get(0, tk.END)
    print('archiver list', archiver_list)

    for label in tkroot.winfo_children():
        if type(label) is tk.Label:
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
    # get folder name, useful to check for path length
    foldername = choosedir.split(os.sep)[-1]

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

    path_info = tk.Label(tkroot, text=f'Processing:\n{choosedir_display}')
    path_info.pack()
    tkroot.update()

    # Create logfile for potential warnings and errors
    log_message(error_file_header)

    all_files = list(pathlib.Path(choosedir).rglob('**/*'))
    for hint in multipart_hint_extensions:
        for file in all_files:
            if file.name.endswith(hint):
                log_message(f"{file.name} seems to be part of a multipart archive, this is not supported and will probably fail.")

    # TODO compressed formats are not processed simultaneously, this needs to be adapted

    arch_files = {}
    if do_zips:
        arch_files['.zip'] = pathlib.Path(choosedir).rglob('**/*.zip')
        arch_files['.7z'] = pathlib.Path(choosedir).rglob('**/*.7z')
        arch_files['.tar'] = pathlib.Path(choosedir).rglob('**/*.tar')
        arch_files['.rar'] = pathlib.Path(choosedir).rglob('**/*.rar')
        nonzipfiles = [x for x in all_files
                       if not x.name.endswith('.zip')
                       and not x.name.endswith('.7z')
                       and not x.name.endswith('.tar')
                       and not x.name.endswith('.rar')]
    else:
        nonzipfiles = all_files
        arch_files['.zip'] = []
        arch_files['.7z'] = []
        arch_files['.tar'] = []
        arch_files['.rar'] = []

    files = []
    # Create tk.Tk label for progress information: counting files
    progress_update_frequency = 10
    progress_info = tk.Label(tkroot, text=f'Listing: {len(files)} files')
    progress_info.pack()
    tkroot.update()
    for ls in nonzipfiles:
        # check for excessive path length locally (in case the user has a problem)
        if len(os.path.join(str(ls.parents[0]), ls.name)) > MAX_PATH:
            log_message(f"WARNING > {MAX_PATH} chars for path + file name: {os.path.join(str(ls.parents[0]), ls.name)}")
        filename = os.path.join(str(ls.parents[0]).replace(choosedir, '.'), ls.name)
        if not filename.endswith(os.sep + '.DS_Store') \
                and not filename.endswith(os.sep + 'Thumbs.db') \
                and not filename.startswith(os.path.join(choosedir, 'ACOUA_md5.md5')) \
                and not filename.startswith(os.path.join('.', 'ACOUA_md5.md5')) \
                and not filename.startswith(os.path.join(choosedir, error_file)) \
                and not filename.startswith(os.path.join('.', error_file)) \
                and not os.path.isdir(filename):
            # check for excessive expected path length locally (where libsafe will fail)
            target_path = libsafe_ingestion_path_prefix + foldername + filename[1:]
            # print(target_path)
            if len(target_path) > MAX_PATH:
                log_message(f"WARNING > {MAX_PATH} chars for expected path + file name: {target_path}")
            #filename = os.path.join([str(ls.parents[0]).replace(choosedir,'.'), ls.name])
            if filename.startswith('/'):
                files.append(filename[1:])
            else:
                files.append(filename)

        if len(files) % progress_update_frequency == 0:
            #print(f'Listing: {len(files)} files')
            progress_info.config(text=f'Listing: {len(files)} files')
            tkroot.update()

    arch_content = {}
    for extension in compressed_extensions:
        arch_content[extension] = {}

    n_archived_files = 0
    for extension in compressed_extensions:
        for ls in arch_files[extension]:
            # Note: .DS_Store and Thumbs.db will not be deleted by Libsafe if contained in Zip and other archive files
            # Libsafe Sanitizers are run before preprocessors such as the Archive Extractor
            (archivename, archive) = open_archive(ls, extension)
            arch_content[extension][archivename] = [archive_object_filename(info) for info in archive_content(archive) if not isdir(info)]

            for content_file in arch_content[extension][archivename]:
                # check for excessive expected path length locally (where libsafe will fail)
                target_path = libsafe_ingestion_path_prefix + foldername + '/' + content_file
                if len(target_path) > MAX_PATH:
                    log_message(f"WARNING > {MAX_PATH} chars for expected path + file name: {target_path}")

            n_archived_files += len(arch_content[extension][archivename])
            progress_info.config(text=f'Listing: {len(files) + n_archived_files} files')
            tkroot.update()
    total_files = len(files) + n_archived_files

    # print('Done listing')
    # the progress information label will now display the actual checksum progress
    # switch to individual file progress frequency: chekcsum is much slower
    progress_update_frequency = 1
    progress = 0
    progress_info .config(text=f'Checksum progress: {progress}/{total_files}')
    tkroot.update()

    f = open("ACOUA_md5.md5", "wb")

    for element in files:
        progress += 1
        try:
            md5 = md5Checksum(element)
            # filenames must be encoded as UTF-8, or they might not match what Libsafe sees on the filesystem
            # also: NFC normalization for proper (composed) representation of accented characters
            f.write(normalize('NFC', f'{md5} {element.replace(choosedir, ".").replace("/", backslash)}\n').encode("UTF-8"))
        except Exception as e:
            trace = str(e)
            log_message(trace)
        if progress % progress_update_frequency == 0:
            #print(f'Progress: {progress}/{len(files)}')
            progress_info.config(text=f'Progress: {progress}/{total_files}')
            tkroot.update()

    for extension in compressed_extensions:
        for myarchfile in arch_content[extension]:
            (archivename, archive) = open_archive(myarchfile, extension)
            archive_path = os.path.sep.join(myarchfile.split(os.sep)[0:-1]).replace(choosedir, '.')
            # print(archive_path)
            for archived_file in arch_content[extension][myarchfile]:
                # Filenames of objects inside a zip are either cp850/cp437 (old style) or utf-8. Let's check
                assumed_encoding = 'cp850' if is_cp850(archived_file) else 'utf-8'
                progress += 1
                try:
                    md5 = md5Checksum(archived_file, ziparchive=archive)
                    # filenames must be encoded as UTF-8, or they might not match what Libsafe sees on the filesystem
                    # Here explicit NFC normalization is not desired: the Libsafe Archive Extractor will manage.
                    f.write(f'{md5} {archive_path + os.path.sep + archived_file.encode(assumed_encoding).decode("utf-8")}\n'.replace("/", backslash).encode("UTF-8"))
                except Exception as e:
                    trace = str(e)
                    log_message(trace)
                if progress % progress_update_frequency == 0:
                    progress_info.config(text=f'Progress: {progress}/{total_files}')
                    tkroot.update()

    f.close()
    progress_info.config(text=f'Progress: {progress}/{total_files}')
    tkroot.update()

    f_err = open(error_file, "r")
    error_content = f_err.read()
    f_err.close()
    
    if error_content.replace('\r', '').replace('\n', '') == error_file_header.replace('\r', '').replace('\n', ''):
        os.remove(error_file)
    else:
        error_info = tk.Label(tkroot, text=error_message)
        error_info.pack()

    done_info = tk.Label(tkroot, text=f'Done: ACOUA_md5.md5 has been created')
    done_info.pack()


root = tk.Tk()
current_font = font.nametofont("TkDefaultFont")
root.wm_title("ACOUA CheckSum v" + version)
width = 400
width_chars = int(1.7*width / current_font.actual()['size'])
root.geometry(f'{width}x550+1000+300')
check_zips = tk.IntVar()
check_zips.set(1)
tk.Checkbutton(root, text="Calculate checksum inside Zip and similar files?", variable=check_zips).pack()
zip_select_lbl = tk.Label(root, text="Zip-like format sequence:")
zip_select_lbl.pack()
frm = tk.Frame()
listbox = tk.Listbox(frm,  selectmode=tk.MULTIPLE)
# TODO discuss standard default
listbox.insert(1, ".zip")
listbox.insert(2, ".7z")
listbox.insert(3, ".rar")
listbox.insert(4, ".zip")

scrollbar = ttk.Scrollbar(frm, orient='vertical')
listbox.config(yscrollcommand=scrollbar.set)
scrollbar.config(command=listbox.yview)

btn_frm = tk.Frame()
for arch_format in compressed_extensions:
    tk.Button(btn_frm, text=f"Add {arch_format}", command=partial(add_archiver, arch_format)).pack(side=tk.LEFT)
btn_frm.pack()
delete_btn = tk.Button(root, text="Delete selected", command=remove_archiver)

scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)
listbox.pack()
frm.pack()
delete_btn.pack()

button_label = 'Select a directory and run checksum'
tk.Button(root, text=button_label, command=partial(runchecksum, root, width_chars, check_zips)).pack()
root.mainloop()
