# This source code is part of the Biotite package and is distributed
# under the 3-Clause BSD License. Please see 'LICENSE.rst' for further
# information.

__author__ = "Patrick Kunzmann"
__all__ = ["create_api_doc", "skip_non_methods"]

from os.path import join, isdir
from os import listdir, makedirs
from importlib import import_module
import types
import json
import enum
from collections import OrderedDict


_indent = " " * 3


# The categories for functions and classes on the module pages
# from biotite/doc/apidoc.json
with open("apidoc.json", "r") as file:
    _pck_categories = json.load(file, object_pairs_hook=OrderedDict)



def create_api_doc(src_path, doc_path):
    """
    Create *.rst files for API documentation.

    Parameters
    ----------
    src_path : str
        The path to the working copy of the *Biotite* package.
    doc_path : str
        The path to the API documentation root directory
        (``biotite/doc/apidoc``).
    """
    # Create directory to store apidoc
    if not isdir(doc_path):
        makedirs(doc_path)
    package_list = _create_package_doc("biotite",
                                       join(src_path, "biotite"),
                                       doc_path)
    _create_package_index(doc_path, package_list)


def _create_package_doc(pck, src_path, doc_path):
    if not _is_package(src_path):
        # Directory is not a Python package/subpackage
        # -> Nothing to do
        return []
    # Identify all subdirectories...
    content = listdir(src_path)
    dirs = [f for f in content if isdir(join(src_path, f))]
    # ... and recursively create also the documentation for them 
    sub_pck = []
    for directory in dirs:
        sub_pck += _create_package_doc(
            f"{pck}.{directory}", join(src_path, directory), doc_path
        )
    
    # Import package (__init__.py) and find all attribute names
    module = import_module(pck)
    attr_list = dir(module)
    # Classify attribute names into classes and functions
    class_list = [attr for attr in attr_list
                  # Do not document private classes
                  if attr[0] != "_"
                  # Check if object is a class
                  and isinstance(getattr(module, attr), type)]
    func_list = [attr for attr in attr_list
                 # Do not document private classes
                 if attr[0] != "_"
                 # All functions are callable...
                 and callable(getattr(module, attr))
                 # ...but classes are also callable
                 and attr not in class_list 
                ]
    ###
    for e in func_list:
        print(e)
    ###
    # Create *.rst files
    _create_package_page(doc_path, pck, class_list, func_list, sub_pck)
    for class_name in class_list:
        _create_class_page(doc_path, pck, class_name)
    for function_name in func_list:
        _create_function_page(doc_path, pck, function_name)
    
    return([pck] + sub_pck)


def _create_package_page(doc_path, package_name,
                         classes, functions, subpackages):
    attributes = classes + functions
    
    # Get categories for this package
    try:
        categories = _pck_categories[package_name]
    except KeyError:
        categories = {}
    # Put all attributes that are not in any category
    # into 'Miscellaneous' category
    misc_attributes = []
    for attr in attributes:
        in_category = False
        for categorized_attributes in categories.values():
            if attr in categorized_attributes:
                in_category = True
        if not in_category:
            misc_attributes.append(attr)
    if len(misc_attributes) > 0:
        # If no other categories exist, call the category 'Content'
        misc_category_name = "Miscellaneous" if categories else "Content"
        categories[misc_category_name] = misc_attributes
    

    # String for categorized class and function enumeration
    category_strings = []
    for category, attrs in categories.items():
        # Create string for each category
        string = \
f"""
{category}
{"-"*len(category)}

.. autosummary::
   :nosignatures:
   :toctree:

"""
        string += "\n".join([_indent + attr for attr in attrs])
        category_strings.append(string)
    # Concatenate strings
    attributes_string = "\n".join(category_strings)

    # String for subpackage enumeration
    subpackages_string = "\n".join(
        [_indent + pck for pck in subpackages]
    )


    # Assemble page
    file_content = \
f"""
{package_name}
{"=" * len(package_name)}
.. currentmodule:: {package_name}

.. automodule:: {package_name}

.. currentmodule:: {package_name}

{attributes_string}

"""
    if len(subpackages) > 0:
        file_content += \
f"""
Subpackages
-----------

.. autosummary::

{subpackages_string}
"""
    with open(join(doc_path, f"{package_name}.rst"), "w") as f:
        f.write(file_content)


def _create_class_page(doc_path, package_name, class_name):
    file_content = \
f"""
{package_name}.{class_name}
{"=" * (len(package_name)+len(class_name)+1)}
.. autoclass:: {package_name}.{class_name}
    :show-inheritance:
    :members:
    :undoc-members:
    :inherited-members:
"""
    with open(join(doc_path, f"{package_name}.{class_name}.rst"), "w") as f:
        f.write(file_content)


def _create_function_page(doc_path, package_name, function_name):
    file_content = \
f"""
{package_name}.{function_name}
{"=" * (len(package_name)+len(function_name)+1)}
.. autofunction:: {package_name}.{function_name}
"""
    with open(join(doc_path, f"{package_name}.{function_name}.rst"), "w") as f:
        f.write(file_content)


def _create_package_index(doc_path, package_list):
    # String for package enumeration
    packages_string = "\n".join(
        [_indent + pck for pck in package_list]
    )
    
    file_content = \
f"""
API Reference
=============

.. autosummary::
   :toctree:

{packages_string}
"""
    with open(join(doc_path, "index.rst"), "w") as f:
        f.write(file_content)


def _is_package(path):
    content = listdir(path)
    return "__init__.py" in content



def skip_non_methods(app, what, name, obj, skip, options):
    """
    Skip all class members, that are not methods, enum values or inner
    classes, since other attributes are already documented in the class
    docstring.
    """
    if skip:
        return True
    if what == "class":
        # Functions
        if type(obj) in [
            types.FunctionType, types.BuiltinFunctionType, types.MethodType
        # Functions from C-extensions
        ] or type(obj).__name__ in [
            "cython_function_or_method", "method_descriptor"
        # Enum Instance or inner class
        ] or isinstance(obj, enum.Enum) or isinstance(obj, type):
            return False
        return True