import sys


class AIEthicsException(Exception):
    def __init__(self,error_message,error_details:sys):
        self.error_message = error_message
        exc_tb = None
        if isinstance(error_message, Exception) and hasattr(error_message, "__traceback__"):
            exc_tb = error_message.__traceback__
        
        if exc_tb is None:
            _,_,tb = error_details.exc_info()
            exc_tb = tb
            
        if exc_tb is not None:
            self.lineno=exc_tb.tb_lineno
            self.file_name=exc_tb.tb_frame.f_code.co_filename 
        else:
            self.lineno = "unknown"
            self.file_name = "unknown"
    
    def __str__(self):
        return "Error occured in python script name [{0}] line number [{1}] error message [{2}]".format(
        self.file_name, self.lineno, str(self.error_message))

        
