import sys, time, socketserver
import emailinfo, regrules, TCGMain
from modules import pyrand, pyemail, pyhash
from queues import Queue
from threading import Thread
from os import walk, makedirs


class TCGServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, request_handler):
        socketserver.TCPServer.__init__(self, server_address, request_handler)


class UserHandler(socketserver.BaseRequestHandler):
    message = {
             'register_username': 'Min 4 characters, max 16 characters.\nEnter desired username: ',
             'register_password': '\nMin 8 characters, max 32 characters. Must have at least 1 letter and number.\nCannot contain symbols.\nEnter password: ',
             'register_email': '\nYour activation code will be sent to this email.\nEnter a valid email: ',
             'activate_username': 'Enter the username of the account you wish to activate: ',
             'activate_password': 'Enter the password of the account you wish to activate: ',
             'activate_email': 'Enter the email you used to register this account: ',
             'activation_code': 'Enter the activation code found in your email: ',
             'act_success': 'Your account has been successfully activated.',
             'invalid_act_code': 'Invalid Username, Password or Activation Code',
             'not_activated': 'This account has not been activated yet.',
             'already_activated': 'That account has already been activated. ',
             'registration_success': 'Your account has been registered and an activation code has been sent to your email.',
             'login_success': 'Successfully logged in.',
             'invalid_up': 'Invalid Username or Password.',
             'login_activate_register': '(L)ogin, (A)ctivate, or (R)egister: ',
             'registration_email': 'Welcome, {0}!\n Thank you for registering your account with pyTCG! Your activation code is:\n{1}\n\n\nCheck out the source code for this TCG: https://github.com/nbness2/TradingCards/'
             }

    def handle(self):
        while True:
            response = send_receive(self.request, self.message['login_activate_register']).lower()
            if response == 'l':
                self.login()
            elif response == 'a':
                self.activate()
            elif response == 'r':
                self.register()
            elif response == '~':
                break
            else:
                send_receive(self.request, 'Invalid choice: '+response, 'n')
        send_receive(self.request, 'Thank you for choosing pyTCG!', 'n')
        self.request.close()

    def login(self):
        socket = self.request
        username = send_receive(socket, 'Username: ', recvsize=16)
        passhash = pyhash.Sha384(send_receive(socket, 'Password: ', recvsize=32)).hexdigest()
        activated, activation_code, user_passhash, user_emailhash = read_user(username)
        activated = int(activated)
        if passhash == user_passhash:
            if activated:
                send_receive(socket, self.message['login_success'], 'n')
            else:
                send_receive(socket, self.message['not_activated'], 'n')
                self.activate(username, passhash)
            self.menu()
        else:
            send_receive(socket, self.message['invalid_up'], 'n')

    def activate(self, username=None, passhash=None):
        socket = self.request
        if not (username and passhash):
            username = send_receive(socket, self.message['activate_username'], recvsize=16)
            passhash = pyhash.Sha384(send_receive(socket, self.message['activate_password'], recvsize=32)).hexdigest()
        user_activated, user_activation_code, user_passhash, user_emailhash = read_user(username)
        user_activated = int(user_activated)
        del user_emailhash
        if user_activated:
            send_receive(socket, self.message['already_activated'], 'n')
        else:
            activation_code = send_receive(socket, self.message['activation_code'], recvsize=11)
            if passhash == user_passhash and activation_code == user_activation_code:
                queues['activation'][0].put(username)
                send_receive(socket, self.message['act_success'], 'n')
            else:
                send_receive(socket, self.message['invalid_act_code'], 'n')

    def register(self):
        socket = self.request
        passed = False
        useremail, password, username = ('', '', '')
        paramchecks = {}
        while not passed:
            if len(paramchecks):
                estring = err_str(paramchecks, ['Username', 'Password', 'Email'])
                send_receive(socket, estring, 'n', 1)
                del estring
            username = send_receive(socket, self.message['register_username'], recvsize=16)
            password = send_receive(socket, self.message['register_password'], stype='p', recvsize=32)
            print(password)
            useremail = send_receive(socket, self.message['register_email'], recvsize=64)
            paramchecks = check_details(username, password, useremail)
            passhash = pyhash.Sha384(password).hexdigest()
            del password
            if type(paramchecks) == bool:
                passed = True
        del paramchecks, passed
        ehash = pyhash.Sha384(useremail.lower()).hexdigest()
        activation_code = pyhash.Md5(pyrand.randstring(16)).hexdigest[::3]
        queues['register'][0].put((username, (0, activation_code, passhash, ehash)))
        emessage = self.message['registration_email'].format(username, activation_code)
        email_params = (useremail, emessage, 'pyTCG activation code', email, emailpass, smtpaddr, False)
        queues['email'][0].put(email_params)
        del username, activation_code, passhash, ehash,
        send_receive(socket, self.message['registration_success'], 'n', 1)

    def menu(self): #cli menu
        pass


class QueueWorker(Thread):
    def __init__(self, params):
        Thread.__init__(self)
        self.queue, self.funct = params

    def run(self):
        while True:
            try:
                if not self.queue.empty():
                    parts = self.queue.get()
                    self.funct(parts)
            except:
                self.queue.put(parts)


def send_receive(socket, sendmsg, stype='i', recvsize=1):
    # Sends encoded data + command, returns decoded receive data
    # n, 0x00 = no input
    # i, 0x01 = input
    # p, 0x02 = password
    # q, 0x09 = quit
    commands = {'n': 0x00, 'i': 0x01, 'p': 0x02, 'q': 0x09}
    send_data = str(commands[stype])+sendmsg
    socket.send(send_data.encode())
    if stype in ('i', 'p'):
        recv_data = socket.recv(64).decode()[:recvsize]
        return recv_data
    socket.recv(64)[:1]


def err_str(errdict, paramorder=()):
    estring = ''
    for param in paramorder if len(paramorder) else errdict.keys():
        if len(errdict[param]):
            estring += '\n'+param+': '
        for error in errdict[param]:
            estring += error+', '
    return estring[:-2]+'\n'


def check_details(username=None, password=None, email=None):
    faults = {'Username': [], 'Password': [], 'Email': []}
    if password:
        passwordc = regrules.check_password(password)
        del password
        if len(passwordc):
            faults['Password'].extend(passwordc)

    if username:
        usernamec = regrules.check_username(username)
        if len(regrules.check_username(username)):
            faults['Username'].extend(usernamec)

    if username.lower() in read_usernames():
        faults['Username'].append('username taken')

    if email:
        emailc = regrules.check_email(email)
        del email
        if type(emailc) != bool:
            faults['Email'].append(emailc)

    for fault in faults:
        if len(faults[fault]):
            print('found fault')
            print(fault)
            return faults
    return True


def read_usernames(userdir='users'):
    return [username[:-4] for username in walk(userdir).__next__()[2]]


def write_user(details, userdir='users/'):
    makedir('users/')
    username, details = details
    username += '.usr'
    with open(userdir+username.lower(), 'w') as ufile:
        for detail in details:
            ufile.write(str(detail)+'\n')
    return True


def read_user(username, userdir='users/'):
    username += '.usr'
    with open(userdir+username.lower(), 'r') as ufile:
        details = tuple([detail.strip() for detail in ufile.readlines()])
    return details


def is_activated(username, userdir='users/'):
    if read_user(username, userdir)[0]:
        return True
    return False


def activate_user(username, userdir='users/'):
    user_details = list(read_user(username, userdir))
    user_details[0] = 1
    write_user((username, user_details), userdir)
    return True


def write_exception(exception, errdir='errors/'):
    with open(errdir+'errors.txt', 'a') as err_file:
        err_file.write(str(exception))


def makedir(path):
    makedirs(path, exist_ok=True)


def start_server(ServerClass, server_addr, RequestHandler):
    server = ServerClass(server_addr, RequestHandler)
    workers = {queue: QueueWorker(queues[queue]) for queue in queues}
    for queue in queues:
        workers[queue].start()
    server.serve_forever()


if __name__ == "__main__":
    queues = {
    'register': [Queue('l'), write_user],
    'activation': [Queue('l'), activate_user],
    'email': [Queue('l'), pyemail.send_email],
    }
    email, emailpass, smtpaddr = emailinfo.info
    HOST = ''
    PORT = 1337
    start_server(TCGServer, (HOST, PORT), UserHandler)
