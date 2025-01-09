import asyncio
from typing import List, Dict, Any, Callable
import json
import os

class UndoManager:
    def __init__(self, logger):
        self.logger = logger
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_steps = 50

    async def execute_action(self, action: Callable[..., Any], *args, **kwargs) -> Any:
        """
        Execute an action and add it to the undo stack.
        
        :param action: Callable action to execute
        :param args: Positional arguments for the action
        :param kwargs: Keyword arguments for the action
        :return: Result of the action
        """
        try:
            result = await asyncio.to_thread(action, *args, **kwargs)
            undo_action = await self.create_undo_action(action, args, kwargs, result)
            self.undo_stack.append(undo_action)
            if len(self.undo_stack) > self.max_undo_steps:
                self.undo_stack.pop(0)
            self.redo_stack.clear()
            return result
        except Exception as e:
            self.logger.error(f"Error executing action {action.__name__}: {str(e)}")
            raise

    async def undo(self) -> Any:
        """
        Undo the last action.
        
        :return: Result of the undo operation
        """
        if not self.undo_stack:
            self.logger.warning("No actions to undo")
            return None

        undo_action = self.undo_stack.pop()
        try:
            result = await asyncio.to_thread(undo_action['undo'])
            self.redo_stack.append(undo_action)
            return result
        except Exception as e:
            self.logger.error(f"Error undoing action: {str(e)}")
            raise

    async def redo(self) -> Any:
        """
        Redo the last undone action.
        
        :return: Result of the redo operation
        """
        if not self.redo_stack:
            self.logger.warning("No actions to redo")
            return None

        redo_action = self.redo_stack.pop()
        try:
            result = await asyncio.to_thread(redo_action['redo'])
            self.undo_stack.append(redo_action)
            return result
        except Exception as e:
            self.logger.error(f"Error redoing action: {str(e)}")
            raise

    async def create_undo_action(self, action: Callable[..., Any], args: tuple, kwargs: dict, result: Any) -> Dict[str, Any]:
        """
        Create an undo action for the given action.
        
        :param action: The original action
        :param args: Arguments of the original action
        :param kwargs: Keyword arguments of the original action
        :param result: Result of the original action
        :return: Dictionary containing undo and redo functions
        """
        undo_func = await self.get_undo_function(action, args, kwargs, result)
        redo_func = lambda: action(*args, **kwargs)
        return {
            'undo': undo_func,
            'redo': redo_func,
            'action_name': action.__name__,
            'args': args,
            'kwargs': kwargs
        }

    async def get_undo_function(self, action: Callable[..., Any], args: tuple, kwargs: dict, result: Any) -> Callable[[], Any]:
        """
        Get the appropriate undo function for the given action.
        
        :param action: The original action
        :param args: Arguments of the original action
        :param kwargs: Keyword arguments of the original action
        :param result: Result of the original action
        :return: Undo function
        """
        if hasattr(action, 'undo'):
            return lambda: action.undo(*args, **kwargs)
        elif action.__name__ == 'create_file':
            return lambda: os.remove(args[0])
        elif action.__name__ == 'delete_file':
            return lambda: self.restore_file(args[0], result)
        elif action.__name__ == 'modify_file':
            return lambda: self.restore_file_content(args[0], kwargs.get('original_content', ''))
        elif action.__name__ == 'rename_file':
            return lambda: os.rename(args[1], args[0])
        else:
            self.logger.warning(f"No specific undo function for action {action.__name__}. Using default (do nothing).")
            return lambda: None

    async def restore_file(self, file_path: str, content: str):
        """
        Restore a deleted file.
        
        :param file_path: Path of the file to restore
        :param content: Content of the file
        """
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            self.logger.info(f"Restored file: {file_path}")
        except Exception as e:
            self.logger.error(f"Error restoring file {file_path}: {str(e)}")
            raise

    async def restore_file_content(self, file_path: str, content: str):
        """
        Restore the content of a file.
        
        :param file_path: Path of the file to restore
        :param content: Original content of the file
        """
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            self.logger.info(f"Restored content of file: {file_path}")
        except Exception as e:
            self.logger.error(f"Error restoring content of file {file_path}: {str(e)}")
            raise

    async def save_state(self, file_path: str):
        """
        Save the current undo/redo state to a file.
        
        :param file_path: Path to save the state file
        """
        state = {
            'undo_stack': self.undo_stack,
            'redo_stack': self.redo_stack
        }
        try:
            with open(file_path, 'w') as f:
                json.dump(state, f)
            self.logger.info(f"Saved undo/redo state to {file_path}")
        except Exception as e:
            self.logger.error(f"Error saving undo/redo state: {str(e)}")
            raise

    async def load_state(self, file_path: str):
        """
        Load the undo/redo state from a file.
        
        :param file_path: Path of the state file to load
        """
        try:
            with open(file_path, 'r') as f:
                state = json.load(f)
            self.undo_stack = state['undo_stack']
            self.redo_stack = state['redo_stack']
            self.logger.info(f"Loaded undo/redo state from {file_path}")
        except Exception as e:
            self.logger.error(f"Error loading undo/redo state: {str(e)}")
            raise

    async def clear_history(self):
        """Clear all undo and redo history."""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.logger.info("Cleared all undo/redo history")

    async def get_undo_history(self) -> List[str]:
        """
        Get a list of action names in the undo stack.
        
        :return: List of action names
        """
        return [action['action_name'] for action in self.undo_stack]

    async def get_redo_history(self) -> List[str]:
        """
        Get a list of action names in the redo stack.
        
        :return: List of action names
        """
        return [action['action_name'] for action in self.redo_stack]
