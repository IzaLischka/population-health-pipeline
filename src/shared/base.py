from typing import Any


class Base:
    """
    Base contract for domain ETL classes.

    Every domain (CKD, Diabetes, Dyslipidemia, Hypertension, Obesity) must
    implement its own subclass of Base, providing concrete extract,
    transform and load steps. This class defines the shared interface only;
    it holds no business logic and no orchestration logic.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    def extract(self, **kwargs: Any) -> Any:
        """Read raw data from its source and return it unmodified."""
        raise NotImplementedError("Subclasses must implement this method")

    def transform(self, **kwargs: Any) -> Any:
        """Apply the domain's transformation rules to the extracted data."""
        raise NotImplementedError("Subclasses must implement this method")

    def load(self, **kwargs: Any) -> Any:
        """Persist the transformed data to its destination layer."""
        raise NotImplementedError("Subclasses must implement this method")
