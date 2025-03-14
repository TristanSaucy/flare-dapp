"""
AI function calling package.
This package contains functions that can be called by AI models.
"""

import inspect
import ai.functions.ethereum as ethereum_module
import ai.functions.sparkdex as sparkdex_module

# Automatically import all functions from the modules
# Filter to only include callable objects (functions) that don't start with underscore
available_functions = {}

# Import Ethereum functions
for name, obj in inspect.getmembers(ethereum_module):
    # Only include callable objects (functions) that don't start with underscore
    if inspect.isfunction(obj) and not name.startswith('_'):
        available_functions[name] = obj

# Import SparkDEX functions
for name, obj in inspect.getmembers(sparkdex_module):
    # Only include callable objects (functions) that don't start with underscore
    if inspect.isfunction(obj) and not name.startswith('_'):
        available_functions[name] = obj

# Make the functions available at the package level
globals().update(available_functions)