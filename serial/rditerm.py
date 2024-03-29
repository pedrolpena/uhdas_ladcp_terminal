''' RDI-specific terminal (BB, WH) for LADCP or moored
ADCP deployment and recovery.

'''
from __future__ import print_function
from future import standard_library
from os.path import expanduser
standard_library.install_hooks()

from six.moves.tkinter import *
from six.moves import tkinter_tkfiledialog
from six.moves import tkinter_messagebox
from six.moves.tkinter_tksimpledialog import askinteger, askstring
import Pmw
import sys, os, select, signal
import logging, logging.handlers
from uhdas.system import logutils

## create log and data directories
#home = expanduser("~")                                           
#logDir = home + '/data/ladp_terminal_logs/'
#dataDir = home + '/data/ladp_proc/raw_ladcp/cut/'

#directory = os.path.dirname(logDir)
#if not os.path.exists(directory):
#    os.makedirs(directory)

#directory = os.path.dirname(dataDir)
#if not os.path.exists(directory):
#    os.makedirs(directory)    




from uhdas.serial.tk_terminal import Tk_terminal, Timeout

import time, termios

import stat
import shutil, re
import tempfile
from threading import Thread
import subprocess





break_msec = 400

## For Mac OSX (darwin): http://fink.sourceforge.net/pdb/package.php/lrzsz

rdi_baud_codes = {300:0, 1200:1, 2400:2,
                  4800:3, 9600:4, 19200:5,
                  38400:6, 57600:7, 115200:8}

# data download rates
default_databauds = {'BB': 38400, 'WH':115200, 'Unrecognized': 9600}

fmt = '%Y/%m/%d  %H:%M:%S'
YM_retry = re.compile(rb"Retry (\d+):")

L = logging.getLogger()
#global logDir
#global dataDir


def time_stamp():
    return time.strftime(fmt, time.gmtime())

class terminal(Tk_terminal):
    def __init__(self, master = None,
                       device = '/dev/ttyS0',
                       baud = 9600,      # communication baud rate
                       data_baud = None, # use default if unspecified
                       Loggers = None,
                       cmd_filename = 'ladcp.cmd',
                       prefix = 'rdi',
                       suffix = 'rdi',
                       cruiseName = 'XXNNNN',
                       backupDir = '',
                       dataLoc = './',
                       logLoc = '',                       
                       stacast = '000_01',
                       datafile_ext = '.dat'):
        Tk_terminal.__init__(self,
                             master=master,
                             device=device,
                             baud=baud,
                             show_cwd=True)
        self.default_baud = baud
        self.data_baud = data_baud
        self.Loggers = Loggers
        self.cmd_filename = cmd_filename
        self.prefix = prefix
        self.suffix = suffix
        self.cruiseName = StringVar()
        self.cruiseName.set(cruiseName)
        self.backupDir = backupDir
        self.dataDir = dataLoc
        self.logDir = logLoc
        self.stacastSV = StringVar()
        self.stacastSV.set(stacast)
# setup logging
        L.setLevel(logging.DEBUG)
        formatter = logutils.formatterTLN
        handler = logging.FileHandler(self.logDir + "rditerm.log")
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        L.addHandler(handler)        
        
        if not datafile_ext.startswith('.'):
            datafile_ext = '.%s' % datafile_ext
        self.datafile_ext = datafile_ext
        self.type = ''         # After wakeup: BB or WH
        self.prefixline = Pmw.LabeledWidget(self.statusframe,
                                            labelpos = 'w',
                                            label_text = 'Prefix:')
        self.prefixline.pack(side = LEFT, anchor = W, padx = 10)
        Label(self.prefixline.interior(),
              width = 3,
              relief = SUNKEN,
              text = self.prefix).pack()
              
        self.suffixline = Pmw.LabeledWidget(self.statusframe,
                                            labelpos = 'w',
                                            label_text = 'Suffix:')
        self.suffixline.pack(side = LEFT, anchor = W, padx = 10)
        Label(self.suffixline.interior(),
              width = 3,
              relief = SUNKEN,
              text = self.suffix).pack()
              
        self.cruiseNameLine = Pmw.LabeledWidget(self.statusframe,
                                            labelpos = 'w',
                                            label_text = 'Cruise:')
        self.cruiseNameLine.pack(side = LEFT, anchor = W, padx = 10)
        self.cruiseNameEntry = Entry(self.cruiseNameLine.interior(),
              width = 10,
              bg = 'white',
              relief = SUNKEN,
              textvariable = self.cruiseName)
              
        self.cruiseNameEntry.pack()
              
                  
              
        self.stacastline = Pmw.LabeledWidget(self.statusframe,
                                            labelpos = 'w',
                                            label_text = 'Station_Cast:')
        self.stacastline.pack(side = LEFT, anchor = W, padx = 10)
        self.stacastentry = Entry(self.stacastline.interior(),
              #relief = SUNKEN,
              width = 10,
              bg = 'white',
              textvariable = self.stacastSV)
        self.stacastentry.pack()
    def add_Loggers(self, Loggers):
        self.Loggers = Loggers

    def start_logging(self):
        if not self.Loggers:
            return
        self.Loggers.start_logging()

    def stop_logging(self):
        if not self.Loggers:
            return
        self.Loggers.check_stop_logging()

    def make_filename(self, ext):
        return "%s%s%s%s%s%s" % (self.prefix,self.cruiseName.get(),'_',self.stacastSV.get(),self.suffix, ext)
                

    def insert(self, msg):
        ''' Insert a comment as if it came from the instrument.
            Add a leading "#" to each line.
        '''
        msg = msg.encode('ascii', 'ignore')
        linelist = msg.splitlines()
        msg1 = b"\n#" + b"\n#".join(linelist) + b"\n"
        self.new_input.put(msg1)

    def start_listening(self, save=True):
        self.stop_logging()
        Tk_terminal.start_listening(self, save=save)

    def set_clock(self):
        self.wake_if_sleeping()
        DateTime = time.strftime('%y%m%d%H%M%S', time.gmtime())
        self.send_commands(('TS%s' % DateTime, ))

    def show_time_ok(self):
        self.wake_if_sleeping()
        t_pc = time.gmtime()
        self.send_commands(('TS?',))
        TSline = self.display.get_line_with('TS').strip()
        tokens = TSline.split()
        if tokens[1] == "=":
            TSstring = tokens[2]  # firmware 51.36
        else:
            TSstring = tokens[1]  # firmware 51.40
        t_adcp = time.strptime(TSstring, '%y/%m/%d,%H:%M:%S')
        dt = time.mktime(t_pc) - time.mktime(t_adcp)
        msg = ('  PC time:   %s\n'
               'ADCP time:   %s\n'
               'PC-ADCP:     %.0f' % (time.strftime(fmt, t_pc),
                                        time.strftime(fmt, t_adcp),
                                        dt))
        self.insert(msg)
        #tkMessageBox.showinfo(message = msg)  # Ugly!
        Pmw.MessageDialog(title = 'Time', message_text = msg,
                          buttons = ('OK',))   #.activate()
        # activate() segfaults on jaunty

    def showconfig(self):
        commands = ('RA','RS','RB0','PS3','B?','C?','E?','P?','T?', 'W?')
        self.wake_if_sleeping()
        self.send_commands(commands)

    def wakeup(self):
        self.Frame.update()
        self.change_baud(self.default_baud)
        self.start_listening(save=False)  # save is irrelevant; port is open
        time.sleep(0.1)
        self.clear_buffer()
        self.send_break(break_msec)
        banner = self.waitfor(b'>', 5)   #1.5
        if banner.find(b'WorkHorse') > -1:
            self.type = 'WH'
        elif banner.find(b'Broadband') > -1:
            self.type = 'BB'
        else:
            L.warning('Wakeup: instrument not identified. Banner:\n%s\n',
                      banner.encode('ascii', 'ignore'))
            tkinter_messagebox.showerror(message='Wakeup: instrument not identified')
            self.type = 'Unrecognized'

    def wake_if_sleeping(self):
        if not self.type:
            self.wakeup()
            return
        try:
            self.start_listening(save=False)
            self.stream.write(b'TS?\r')
            self.stream.flush()
            self.waitfor(b'>',1)
        except Timeout:
            self.wakeup()


    def wakeup_showtime(self):
        self.wakeup()
        self.show_time_ok()

    def sleep(self):
        self.change_baud(self.default_baud)
        self.wake_if_sleeping()
        self.stream.write(b'CZ' + b'\r')
        self.stream.flush()
        if self.type == 'BB':
            self.waitfor('[POWERING DOWN .....]', 2)
        else:
            self.waitfor('Powering Down', 5)


    def run_diagnostics(self):
        self.wake_if_sleeping()
        diagnostics = ('PS0', 'PT200')
        self.send_commands(diagnostics)


    def eraserecorder(self):
        self.change_baud(self.default_baud)
        self.start_listening(save=False) # save is irrelevant; port is open
        self.wake_if_sleeping()
        self.stream.write(b'RE ErAsE' + b'\r')
        self.stream.flush()
        self.waitfor(b'>', 5)

    def send_commands(self, commands, timeout=None):
        if timeout is None:
            timeout = 2  # short timeout is OK with streamwaitfor
        self.start_listening(save=False)
        for cmd in commands:
            self.stream.write(cmd.rstrip().encode('ascii', 'ignore') + b'\r')
            self.stream.flush()
            self.streamwaitfor(b'>', timeout=timeout)

    @staticmethod
    def _validated_commands(self,fname):
        '''
        Return commands from file with comments.
        Remove CK and CS, if present, because we add these later.
        Other validation could be done, but is not at present.
        '''
        lines = open(fname, 'r').readlines()
        cmds = []
        for line in lines:

            line = line.split('#',1)[0]
            line.strip()
           
            line = line.split(';',1)[0]
            line.strip()
            
            line = line.split('$',1)[0]
            line.strip()
            
            if line and not line.startswith('CK') and not  line.startswith('CS'):
                cmds.append(line)
        return cmds

    def send_setup(self):
        self.wake_if_sleeping()
        fn = self.cmd_filename
        L.info("Sending command file: %s", fn)
        self.insert("Sending command file: %s" % (fn,))

        try:
            cmds = self._validated_commands(self,fn)
            self.send_commands(cmds)
            self.stream.write(b'CK' + b'\r')
            self.stream.flush()
            self.waitfor('[Parameters saved as USER defaults]', 2)
            self.stream.write(b'CS' + b'\r')
            self.stream.flush()
        except Timeout:
            L.exception('Timeout while sending commands')
            tkinter_messagebox.showerror(message='Timout while sending commands')
            return
        except IOError:
            L.exception("looking for file %s", fn)
            tkinter_messagebox.showerror(message = "Can't find or read file %s" % (fn,))
            self.ask_send_setup()

        time.sleep(1)
        L.info("Data collection started")
        self.insert("Data collection started, %s\n" % time_stamp())
        logfilename = self.make_filename(".log")
        logfilename = self.logDir + logfilename
        self.append_to_file(logfilename)
        self.insert("Deployment logfile written to %s" % logfilename)
        self.stop_listening()


    def ask_send_setup(self):
        if os.path.exists(self.cmd_filename):
            initialfile = self.cmd_filename
        else:
            initialfile=''
        fn = tkinter_tkfiledialog.askopenfilename(initialfile = initialfile,
                       initialdir = os.getcwd(),
                       filetypes = (('Command', '*.cmd'), ('All', '*')),
                       parent = self.Frame,
                       title = 'Command file')
        if not fn: return
        self.cmd_filename = fn
        self.send_setup()



    def no_ask_send_setup(self):
        if os.path.exists(self.cmd_filename):
            self.send_setup()
            return
        else:
            initialfile=''
            fn = tkinter_tkfiledialog.askopenfilename(initialfile = initialfile,
                           initialdir = os.getcwd(),
                           filetypes = (('Command', '*.cmd'), ('All', '*')),
                           parent = self.Frame,
                           title = 'Command file')
        if not fn: return
        self.cmd_filename = fn
        self.send_setup()


    # This may not be useful; it is supposed to
    # get a single ensemble in hex-ascii mode.
    def start_ascii(self):
        self.wake_if_sleeping()
        self.stream.write(b'CF01010\r')
        self.stream.flush()
        termios.tcdrain(self.fd)
        self.stream.write(b'CS\r')
        self.stream.flush()
        termios.tcdrain(self.fd)
        self.waitfor(b'>')


    # ping at will
    def start_binary(self, cmdlist = None):
        self.wake_if_sleeping()
        self.set_clock()
        if cmdlist:
            self.send_commands(cmdlist)
        self.stream.write(b'CF11110\r') # serial out, no recorder
        self.stream.flush()
        termios.tcdrain(self.fd)
        self.change_all_baud()
        self.stream.write(b'CS\r')
        self.stream.flush()
        termios.tcdrain(self.fd)
        self.waitfor(b'CS\r\n')
        self.stop_listening(restore=False)
        self.start_logging()

    def get_data_baud(self):
        if self.data_baud is None:
            db = default_databauds.get(self.type, self.default_baud)
            return db
        return self.data_baud

    def change_all_baud(self, baud = None):
        if baud is None:
            baud = self.get_data_baud()

        # TODO: figure out why the following line occasionally
        # times out within end_ymodem_download.
        self.send_commands([''])

        self.stream.write(b'CB%d11\r' % (rdi_baud_codes[baud],))
        self.stream.flush()
        termios.tcdrain(self.fd)
        self.waitfor(b'>', 3)
        self.change_baud(baud)
        time.sleep(0.5) # ad hoc; without delay, local serial port
                        # baud rate does not seem to take effect
                        # before we send a command and receive
                        # a response.
                        # A delay was added to the serialport module;
                        # we may not need this additional delay here.

    def list_recorder(self):
        if self.type == 'BB':
            cmds = ('RA', 'RS')
        else:
            cmds = ('RA', 'RS', 'RF', 'RR')
        try:
            self.send_commands(cmds)
        except Timeout:
            self.wakeup()
            self.send_commands(cmds)

    def find_filename(self):
        '''For BB instrument, get name of last file downloaded.'''
        line = self.display.get_line_with('Receiving:').strip()
        filename = line.split()[1]
        L.info("in find_filename, found: %s", filename)
        return filename

    def find_number_recorded(self):
        try:
            self.send_commands(('RA',))
        except Timeout:
            self.wakeup()
            self.send_commands(('RA',))
        if self.type == 'BB':
            ii = 2
        else:
            ii = 1
        line = self.display.get_lines_from('RA')
        return int(line.split()[ii])


    def download(self):
        """
        download menu item callback: start the download process
        """
        self.wake_if_sleeping()
        nrec = self.find_number_recorded()
        ndown = askinteger('Download',
                'File to download, %d to %d' % (1, nrec),
                initialvalue = nrec,
                minvalue = 1,
                maxvalue = nrec)
        if ndown is None:
            return

        self.ymodem_download(ndown)



    def run_ymodem(self):
        """
        Execute the ymodem download program, 'rb'.

        This is run in a separate thread, which exits when
        the ymodem program exits.
        """

        d = self.get_device()
        rp, wp = os.pipe()   # read_pipe, write_pipe
        if sys.platform == 'darwin':
            cmd_args = "lrb -v --rename < %s > %s " % (d, d)
        else:
            cmd_args = "rb --rename < %s > %s " % (d, d)
        ymp = subprocess.Popen(cmd_args, shell=True, cwd=self.ymdir,
                                stderr=wp)
        running = True
        while running:
            # Select provides a timeout so self.canceled is checked.
            rd, wr, er = select.select([rp], [], [], 0.1)
            if rp in rd:
                cc =  os.read(rp, 500)
                cc = cc.replace(b'\r', b'\n')
                if cc:
                    self.new_input.put(cc)  # via queue to main thread
                    if self.save:
                        self.outfile.write(cc)
            if self.canceled:
                try:
                    ymp.terminate() # python 2.6
                except AttributeError:
                    os.kill(ymp.pid, signal.SIGTERM)
                termios.tcflush(os.open(d, os.O_RDWR), termios.TCIOFLUSH)

            returncode = ymp.poll()
            if returncode is not None:
                L.info("in run_ymodem, ymp.poll returncode is %s", returncode)
                running = False
            time.sleep(0.001) # Seems to be necessary, contrary to Grayson.
        termios.tcflush(os.open(d, os.O_RDWR), termios.TCIOFLUSH)
        os.close(rp)
        os.close(wp)
        self.listening = False  # otherwise start_listening will not work right
        self.end_ymodem_download()

    def abort_download(self):
        """
        callback for Cancel button; signal the thread to end
        """
        self.canceled = 1
        #self.thread2.join()

    def ymodem_download(self, filenum = None):
        # filenum is None for all files (WH only); otherwise file number
        #            directory selection; for now it is in current directory
        self.ymdir = tempfile.mkdtemp(dir=self.dataDir)
        self.insert("Initial download directory: %s" % self.ymdir)
        dbaud = self.get_data_baud()
        self.change_all_baud(dbaud)

        if filenum:
            self.stream.write(b'RY%d\r' % filenum)
        else:
            self.stream.write(b'RY\r')
        self.stream.flush()
        if self.type == 'WH':
            self.waitfor(b'now')
        self.stop_listening(restore=False)

        self.canceled = 0
        self.set_status("Ymodem download on %s at %d baud."
                                % (self.get_device(), dbaud))
        self.b_cancel = Button(self.toprow, text = 'Cancel Download',
                          command = self.abort_download)
        self.b_cancel.pack(side = RIGHT, expand = NO, fill = NONE)
        self.menubar.disableall()
        self.Frame.update()
        self.clear_buffer()
        self.thread2 = Thread(target = self.run_ymodem)
        self.thread2.setDaemon(1)
        self.thread2.start()
        self.listening = 1
        self.update()

    def end_ymodem_download(self):
        self.menubar.enableall()
        self.b_cancel.destroy()
        self.Frame.update()
        # Count retries in buffer before start_listening, which
        # erases the buffer.
        nretry = 0
        for m in YM_retry.finditer(self.buffer):
            nretry +=  1
        self.start_listening(save=False)

        # For unknown reasons, the following baud change can
        # time out at the initial "send_commands(['']" line.
        # We don't want this to block completing the finish_downloads
        # operation.
        try:
            self.change_all_baud(self.default_baud)
        except Timeout:
            L.warn("Timeout at change_all_baud in end_ymodem_download")

        if self.canceled:
            L.info("cancelled download")
            self.insert("DOWNLOAD CANCELED")
            return

        self.insert("ymodem download number of retries: %d" % nretry)
        self.Frame.after_idle(self.finish_download)

    def finish_download(self):
        logfilename = self.make_filename(".log")
        logfilename = self.logDir + logfilename
        fn0 = self.find_filename()
        fn0 = os.path.join(self.ymdir, fn0)
        #fn0 = dataDir + '/' + fn0        

        try:
            os.utime(fn0, None)
            nbytes = os.stat(fn0)[stat.ST_SIZE]
        except OSError as exc:
            msglines = [str(exc)]
            msglines.append('This should be the file that was just downloaded.')
            msglines.append('Quitting without renaming or backup.')
            for line in msglines:
                self.insert(line)
            self.append_to_file(logfilename)
            tkinter_messagebox.showerror(message='\n'.join(msglines))
            return

        self.insert("Downloaded file %s has %d bytes" % (fn0, nbytes))

        fn = self.dataDir + self.make_filename(self.datafile_ext)
        fn1 = None
        while fn1 is None:
            fn1 = askstring('Rename', 'Rename %s to:' % fn0,
                    initialvalue = fn)
                    
            if fn1 is None:
                break
            if os.path.exists(fn1):
                tkinter_messagebox.showerror(message="File %s already exists" % fn1)
                fn1 = None
        if fn1:
            self.insert("File written as %s" % fn1)			
            os.rename(fn0, fn1)

        else:
            fn1 = fn0
        os.chmod(fn1, 0o444) # Read-only.
        if self.backupDir:
            if not os.access(self.backupDir, os.W_OK):
                try:
                    os.mkdir(self.backupDir)
                except Exception as exc:
                    msglines = [str(exc)]
                    msglines.append(
                        "Could not make backup directory %s" % self.backupDir)
                    msglines.append(
                        "If it already exists, check its permissions")
                    for line in msglines:
                        self.insert(line)
                    tkinter_messagebox.showerror(message='\n'.join(msglines))
                    L.warning('\n'.join(msglines))
                    self.backupDir = None
        if self.backupDir:
            try:
                shutil.copy2(fn1, self.backupDir + os.path.basename(fn1))
                self.insert("File %s backed up to %s" % (os.path.basename(fn1), self.backupDir))
            except Exception as exc:
                msglines = [str(exc)]
                msglines.append("Backup to %s failed." % self.backupDir)
                for line in msglines:
                    self.insert(line)
                tkinter_messagebox.showerror(message='\n'.join(msglines))
        self.append_to_file(logfilename)
        self.insert("Recovery logfile appended to %s" % logfilename)
        self.sleep()
        try:
            os.rmdir(self.ymdir)
        except OSError:
            pass


    def append_to_file(self, fn):
        try:
            f = open(fn, 'ab')       # open in binary mode so a
                                     # junk character won't trigger
                                     # UnicodeEncodeError

            txt = self.display.get().encode('utf-8')#2/9/16 added encode to avoid unicode error. Pedro Pena
            f.write(txt)
            f.close()
        except:
            L.exception("writing to file <%s>", fn)
            tkinter_messagebox.showerror(message = "Can't write to file %s" % fn)

    def start_deploy_recover(self):
        self.clear()
        self.insert("***************************** %s\n" % time_stamp())
        self.wakeup_showtime()
        self.list_recorder()

    def make_menu(self, master):
        Tk_terminal.make_menu(self, master)
        mb = self.menubar
        mb.deletemenuitems('Command', 0)

        mb.addmenuitem('Command', 'command', '',
                       label = 'Wakeup',
                       command = self.wakeup)
        mb.addmenuitem('Command', 'command', '',
                       label = 'ZZZZ (go to sleep)',
                       command = self.sleep)
        mb.addmenuitem('Command', 'command', '',
                       label = 'Set Clock',
                       command = self.set_clock)
        mb.addmenuitem('Command', 'command', '',
                       label = 'Send Setup',
                       command = self.ask_send_setup)
        mb.addmenuitem('Command', 'command', '',
                       label = 'Show Config',
                       command = self.showconfig)

        mb.addmenuitem('Command', 'command', '',
                       label = 'Run Diagnostics  ',
                       command = self.run_diagnostics)

        mb.addmenuitem('Command', 'command', '',
                       label = 'Change to download Baud',
                       command = self.change_all_baud)
        mb.addmenuitem('Command', 'command', '',
                       label = 'Start Binary',
                       command = self.start_binary)
        mb.addmenuitem('Command', 'command', '',
                       label = 'List Recorder Directory',
                       command = self.list_recorder)

        mb.addmenuitem('Command', 'command', '',
                       label = 'Erase Recorder NOW',
                       command = self.eraserecorder)


        mb.addmenu('Deploy', '')
        mb.addmenuitem('Deploy', 'command', '',
                       label = 'Deployment Initialization',
                       command = self.start_deploy_recover)
        mb.addmenuitem('Deploy', 'command', '',
                       label = 'Set Clock',
                       command = self.set_clock)
        mb.addmenuitem('Deploy', 'command', '',
                       label = 'Send Setup and Start',
                       command = self.ask_send_setup)
        mb.addmenuitem('Deploy', 'command', '',
                       label = 'Send Setup and Start Without Asking',
                       command = self.no_ask_send_setup)                       
        # There seems to be no point in making this a separate step.
        #mb.addmenuitem('Deploy', 'command', '',
        #               label = 'Disconnect',
        #               command = self.stop_listening)


        mb.addmenu('Recover', '')
        mb.addmenuitem('Recover', 'command', '',
                       label = 'Recovery Initialization',
                       command = self.start_deploy_recover)
        mb.addmenuitem('Recover', 'command', '',
                       label = 'Download',
                       command = self.download)

def main():
    from optparse import OptionParser
    op = OptionParser()
    op.add_option('-d', '--device', dest = "device",
                   help = ('DEVICE is the full path of serial device;' +
                             ' default is /dev/ttyS0'),
                   default = '/dev/ttyS0')
    op.add_option('-p', '--prefix', dest = "prefix",
                   help = 'prefix of default name for downloaded file',
                   default = 'ladcp')
    op.add_option('-b', '--backup', dest = "backup",
                   help = 'directory for automatic backup',
                   default = '')
    op.add_option('', '--baud', dest = "baud", type = 'int',
                   help = 'default baud rate',
                   default = 9600)
    op.add_option('', '--download', dest = "data_baud", type = 'int',
                   help = 'download baud rate',
                   default = None)
    op.add_option('-s', '--stacast', dest = "stacast",
                   help = 'Station_Cast, e.g., 057_01, for file naming',
                   default = '000_00')
    op.add_option('-e', '--datafile_ext', dest = "datafile_ext",
                   help = 'extension for downloaded data files',
                   default = 'dat')
    op.add_option('-c', '--command', dest = "cmd_filename",
                   help = "Setup command filename",
                   default = 'ladcp.cmd')

    o, a = op.parse_args()

    R = terminal(device = o.device, master = None,
                   baud = o.baud,
                   data_baud = o.data_baud,
                   prefix = o.prefix,
                   backupDir = o.backupDir,
                   dataDir = o.dataLoc,
                   logDir = o.logLoc,
                   stacast = o.stacast,
                   datafile_ext = o.datafile_ext,
                   cmd_filename = o.cmd_filename)
            
    logfilename = 'rditerm_%s.log' % os.path.split(o.device)[-1]
    logfilename = logDir + logfilename
    print("Saving terminal IO to %s." % logfilename)
    R.begin_save(logfilename)
    R.master.mainloop()
