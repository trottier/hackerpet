# coding: utf-8

__author__ = "Michael Gschwandtner"
__copyright__ = "Copyright 2019, Michael Gschwandtner"
__credits__ = ["Michael Gschwandtner"]
__license__ = "MIT"
__version__ = "1.0.0"
__maintainer__ = "Michael Gschwandtner"
__email__ = "mgschwan@gmail.com"
__status__ = "Development"


import logging
import threading
import socket
import select
import time

def decode_buttons(state):
    return [(state & 1) > 0, (state & 2) > 0, (state & 4) > 0 ]

class Cleverpet:
    host = None
    port = None
    thread = None
    running = False
    buffer = ""
    socket = None
    send_queue = []

    waiting_for_dispense = False
    treat_taken = False

    wait_for_button_press = False
    buttons_pressed = [False,False,False]


    def __init__(self, host, port):
        self.host = host 
        self.port = port

    def connect(self):
        self.send_queue = []
        if not self.thread:
            self.thread = threading.Thread(target=self._run)
            self.thread.start()

    def _send(self, msg):
        self.send_queue.append(msg)

    def _process_message(self, msg):
        start = msg.find("@")
        end = msg.find(";")
        tmp = msg[start+1:end]
        fields = tmp.split(":")
        command = ""
        parameters = []
        logging.debug (f"Decoding message '{tmp}'")
        if len(fields) > 0:
            command = fields[0]
            parameters = fields[1:]

            if command == "buttons":
                logging.debug ("Received button state")
                if len(parameters) > 0:
                    state = 0
                    try:
                        state = int(parameters[0])
                    except ValueError:
                        pass
                    buttons = decode_buttons(state)
                    print (str(buttons))
            elif command == "button_event":
                logging.debug ("Received button press")
                if len(parameters) > 0:
                    state = 0
                    try:
                        state = int(parameters[0])                       
                    except ValueError:
                        pass
                    buttons = decode_buttons(state)
                    if self.wait_for_button_press:
                        self.buttons_pressed = buttons[:]
                        self.wait_for_button_press = False
            elif command == "ok":
                logging.debug ("Received acknowledgement")
                if len(parameters) > 0:
                    if parameters[0] == "taken":
                      self.treat_taken = True
                      self.waiting_for_dispense = False
                    elif parameters[0] == "not_taken":
                      self.treat_taken = False
                      self.waiting_for_dispense = False
                    else:
                        logging.debug ("Unknown ack")
            elif command == "error":
                logging.debug ("Dispenser had an error")
                self.treat_taken = False
                self.waiting_for_dispense = False

    def _run(self):
        logging.debug ("Starting Thread")
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host,self.port))    

        idx = 0

        while self.running:

            """ RECEIVE """
            data = self.read_until(";")
            if data:
                logging.debug (f"Received: {data}")
                self._process_message(data)
            else:
                #Prevent busy waiting to keep the CPU usage in check
                time.sleep(0.005)
                
            """ SEND """
            send_msg = None
            try:
                readable,writeable,exceptions = select.select([],[self.socket],[],0)
                if writeable:
                    send_msg = self.send_queue.pop(0)
                    self.socket.sendall(send_msg.encode())
                    logging.debug (f"Sent: {send_msg}")
            except IndexError:
                #Prevent busy waiting to keep the CPU usage in check
                time.sleep(0.005)


        self.thread = None
        self.socket.close()

    def read_until(self, delimiter):
        retVal = None
        readable,writable,exceptions = select.select([self.socket],[],[],0)
        while readable:
            c = self.socket.recv(1).decode()
            self.buffer += c
            if c == delimiter:
                retVal = self.buffer
                self.buffer = ""
                break
            readable,writable,exceptions = select.select([self.socket],[],[],0)
        return retVal

    def join(self):
        if self.thread:
            self.thread.join()

    def disconnect(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def all_buttons_off(self):
        self.button_color(0,"off")
        self.button_color(1,"off")
        self.button_color(2,"off")

    def button_color(self, button, color):
        yellow = 0
        blue = 0

        if color in ["yellow", "white"]:
            yellow = 60
        if color in ["blue", "white"]:
            blue = 60

        self._send(f"@light:{button}:{yellow}:{blue}:;")

    def wait_for_button(self, timeout = 1.0):
        start = time.time()
        self.wait_for_button_press = True
        retVal = [False,False,False]
        while time.time() < start + timeout:
            if not self.wait_for_button_press:
                retVal = self.buttons_pressed[:]
                break
        return retVal

    def dispense(self):
        self.waiting_for_dispense = True
        self.treat_taken = False
        self._send("@dispense;")
        retVal = False
        while self.waiting_for_dispense:
            time.sleep(0.01)
        retVal = self.treat_taken
        self.treat_taken = False
        return retVal    

    def new_round(self):
        self._send("@reinitialize;")
    
    def positive_sound(self):
        self.play_audio("positive")

    def negative_sound(self):
        self.play_audio("negative")

    def do_sound(self):
        self.play_audio("do")

    def click_sound(self):
        self.play_audio("click")

    def squeak_sound(self):
        self.play_audio("squeak")

    def left_sound(self):
        self.play_audio("left")

    def middle_sound(self):
        self.play_audio("middle")

    def right_sound(self):
        self.play_audio("right")

    def play_audio(self, sound):
        self._send(f"@playaudio:{sound}:;")

