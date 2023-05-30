# This contains all of the run commands used by the ds_validation library

class RunCommand():

    def __init__(self,
            args='',
            merchants='',
            source='',
            logging=True,
            no_error=False
        ):
        '''
        Parameters:
            args: str, list of custom arguments joined into a string to append to command
            merchants: str, gives all of the merchants in a joined string to run for
            source: str, specifies a particular data source we desire to pull the data from
            logging: boolean, indicates if we should send results to ouput loggin dashboard
            no_error: boolean, indicates command is for Picker test/suite and should pass/fail only
        '''
        self.args = args
        self.merchants = merchants
        self.source = source
        self.logging = logging
        self.no_error = no_error
        print(self.no_error)

        # Test suite command
        if self.no_error is True:
            self.command = 'python 3.8 -m sources.comparison -ne'

        else:
            # Start with base command we always use
            _base_command = 'python3.8 -m sources.comparison'

            # Merchants argument
            if self.merchants != '':
                _base_command += f' -ra -mer {self.merchants}'

            # Source argument
            if self.source != '':
                _base_command += f' -source {self.source}'

            # Custom argument list
            if self.args != '':
                _base_command += self.args

            # Logging argument
            if self.logging is True:
                _base_command += ' -ul'

            # Final command to run
            self.command = _base_command

class NoLoggingCommand(RunCommand):
    '''
    Basic command with logging to the master dashboard disabled
    '''
    logging = False

class NoErrorCommand(RunCommand):
    '''
    Picker test suite, gives simple pass/fail
    '''
    args = ' -ne'
    logging = False
    no_error = True

    def __init__(self, merchants=None, source=None):
        self.merchants = merchants
        self.source = source

        # Init base run command with Picker Test Suite attributes
        super().__init__(
            args=self.args, 
            merchants=self.merchants, 
            source=self.source, 
            logging=self.logging, 
            no_error=self.no_error
        )
