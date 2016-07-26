
def check_username(username):
    #username length between 4 and 16
    #username cannot contain symbols
    #must not be taken
    faults = []
    if not 4 < len(username) < 16:
        faults.append('too long\short')
    if not username.isalnum():
        faults.append('can only contain alphanumeric characters')
    return faults


def check_password(password):
    #password length between 8 and 32
    #password must have at least 1 number and 1 letter
    #password cannot contain symbols
    faults = []
    if not 8 <= len(password) <= 32:
        faults.append('too long\short')
    if not password.isalnum():
        faults.append('can only contain alphanumeric characters')
    if password.isalpha() or password.isnumeric():
        faults.append('must have at least 1 letter and number')
    return faults


def check_email(email):
    #must look like an email. If they don't get email it is because they entered wrong.
    esplit = email.split('@')
    if '@' not in email or '.' not in esplit[0] or (len(esplit[0].split('.')[0]) <= 1 or len(esplit[0].split('.')[1]) <= 1):
        return ('invalid email')
    return True
