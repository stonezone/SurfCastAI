"""
Base data processor for SurfCastAI.
"""

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar

from ..core.bundle_manager import BundleManager
from ..core.config import Config

# Generic type variables for input and output types
T_Input = TypeVar("T_Input")
T_Output = TypeVar("T_Output")


class ProcessingResult:
    """
    Result of a processing operation.

    Attributes:
        success: Whether processing was successful
        data: Processed data (if successful)
        error: Error message (if not successful)
        warnings: List of warning messages
        metadata: Additional metadata
    """

    def __init__(
        self,
        success: bool = True,
        data: Any = None,
        error: str | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Initialize ProcessingResult.

        Args:
            success: Whether processing was successful
            data: Processed data
            error: Optional error message
            warnings: Optional list of warning messages
            metadata: Optional metadata dictionary
        """
        self.success = success
        self.data = data
        self.error = error
        self.warnings = warnings or []
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "success": self.success,
            "error": self.error,
            "warnings": self.warnings,
            "metadata": self.metadata,
            # Note: 'data' is not included as it may be complex
        }

    def __bool__(self) -> bool:
        """
        Boolean representation (True if successful).

        Returns:
            Boolean success value
        """
        return self.success


class DataProcessor(Generic[T_Input, T_Output], ABC):
    """
    Abstract base class for data processors.

    Features:
    - Standardized interface for data processing
    - Validation capabilities
    - Comprehensive error handling
    - Result tracking
    """

    def __init__(self, config: Config):
        """
        Initialize the data processor.

        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"processor.{self.__class__.__name__.lower()}")

    @abstractmethod
    def process(self, data: T_Input) -> ProcessingResult:
        """
        Process data.

        Args:
            data: Input data to process

        Returns:
            ProcessingResult with processed data or error
        """
        pass

    def validate(self, data: T_Input) -> list[str]:
        """
        Validate input data before processing.

        Args:
            data: Input data to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        # Default implementation - no validation
        return []

    def process_with_validation(self, data: T_Input) -> ProcessingResult:
        """
        Process data with validation.

        Args:
            data: Input data to process

        Returns:
            ProcessingResult with processed data or error
        """
        try:
            # Validate input data
            validation_errors = self.validate(data)
            if validation_errors:
                return ProcessingResult(
                    success=False, error="Validation failed", warnings=validation_errors
                )

            # Process data
            return self.process(data)

        except Exception as e:
            self.logger.error(f"Error processing data: {e}")
            return ProcessingResult(success=False, error=f"Processing error: {str(e)}")

    def process_file(self, file_path: str | Path) -> ProcessingResult:
        """
        Process data from a file.

        Args:
            file_path: Path to the file

        Returns:
            ProcessingResult with processed data or error
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return ProcessingResult(success=False, error=f"File not found: {file_path}")

        try:
            # Read file content
            with open(file_path) as f:
                content = f.read()

            # Parse JSON if file is JSON
            if file_path.suffix.lower() in [".json"]:
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    return ProcessingResult(
                        success=False, error=f"Invalid JSON in {file_path}: {e}"
                    )
            else:
                # Use raw content for non-JSON files
                data = content

            # Process data
            return self.process_with_validation(data)

        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            return ProcessingResult(success=False, error=f"Error processing file: {str(e)}")

    def process_bundle(
        self, bundle_id: str | None = None, file_pattern: str | None = None
    ) -> list[ProcessingResult]:
        """
        Process files from a data bundle.

        Args:
            bundle_id: Bundle ID (uses latest if not provided)
            file_pattern: Optional pattern to filter files (e.g., 'buoy_*.json')

        Returns:
            List of ProcessingResult objects
        """
        self.logger.info(
            f"process_bundle called: bundle_id={bundle_id}, file_pattern={file_pattern}"
        )

        # Get bundle manager
        bundle_manager = BundleManager(self.config.data_directory)

        # Get bundle path
        bundle_path = bundle_manager.get_bundle_path(bundle_id)
        if bundle_path is None:
            self.logger.error(f"Bundle not found: {bundle_id}")
            return [ProcessingResult(success=False, error=f"Bundle not found: {bundle_id}")]

        # Get files from bundle
        if file_pattern:
            self.logger.info(f"About to glob: bundle_path={bundle_path}, pattern={file_pattern}")
            files = list(bundle_path.glob(file_pattern))
            self.logger.info(
                f"Found {len(files)} files matching pattern '{file_pattern}' in {bundle_path}"
            )
        else:
            # Use file_list method from bundle_manager
            file_list = bundle_manager.get_bundle_file_list(bundle_id)
            files = []
            for file_info in file_list:
                file_path = file_info.get("file_path")
                if file_path:
                    files.append(Path(file_path))

        if not files:
            self.logger.warning(f"No files found in bundle {bundle_id}")
            return [ProcessingResult(success=False, error=f"No files found in bundle {bundle_id}")]

        # Process each file
        results = []
        for file_path in files:
            results.append(self.process_file(file_path))

        return results

    def save_result(
        self, result: ProcessingResult, output_path: str | Path, overwrite: bool = False
    ) -> bool:
        """
        Save processing result to a file.

        Args:
            result: Processing result to save
            output_path: Path to save the result
            overwrite: Whether to overwrite existing file

        Returns:
            True if saved successfully, False otherwise
        """
        output_path = Path(output_path)

        # Check if file exists and overwrite is False
        if output_path.exists() and not overwrite:
            self.logger.warning(f"File already exists: {output_path}")
            return False

        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Determine the format based on file extension
            if output_path.suffix.lower() == ".json":
                # Try to serialize to JSON
                data = result.data
                if hasattr(data, "to_json"):
                    # Use to_json method if available
                    with open(output_path, "w") as f:
                        f.write(data.to_json())
                elif hasattr(data, "to_dict"):
                    # Use to_dict method if available
                    with open(output_path, "w") as f:
                        json.dump(data.to_dict(), f, indent=2)
                else:
                    # Try direct JSON serialization
                    with open(output_path, "w") as f:
                        json.dump(data, f, indent=2)
            else:
                # Default to string representation
                with open(output_path, "w") as f:
                    f.write(str(result.data))

            self.logger.info(f"Saved result to {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving result to {output_path}: {e}")
            return False
