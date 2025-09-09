from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAnalysisProcess(ABC):
    """
    Base abstract class for transcript analysis processes.
    
    All analysis process implementations must inherit from this class
    and implement the required methods.
    """
    
    @abstractmethod
    def analyze(self, transcript_data: Dict[Any, Any], call_metadata: Dict[Any, Any]) -> Dict[Any, Any]:
        """
        Analyze a transcript and extract structured information.
        
        Args:
            transcript_data: Preprocessed transcript data
            call_metadata: Metadata about the call
            
        Returns:
            Dict with structured analysis results
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the name of this analysis process.
        
        Returns:
            Process name string
        """
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """
        Get a description of this analysis process.
        
        Returns:
            Process description string
        """
        pass 