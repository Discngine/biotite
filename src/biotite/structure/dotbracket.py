# This source code is part of the Biotite package and is distributed
# under the 3-Clause BSD License. Please see 'LICENSE.rst' for further
# information.

"""
This module handles conversion of RNA structures to
dot-bracket-notation.
"""

__name__ = "biotite.structure"
__author__ = "Tom David Müller"
__all__ = ["dot_bracket_from_structure", "dot_bracket",
    "base_pairs_from_dot_bracket"]

import numpy as np
from .basepairs import base_pairs
from .pseudoknots import pseudoknots
from .residues import get_residue_count, get_residue_positions

_OPENING_BRACKETS = "([<ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_OPENING_BRACKETS_BYTES = bytearray(_OPENING_BRACKETS.encode())
_CLOSING_BRACKETS = ")]>abcdefghijklmnopqrstuvwxyz"
_CLOSING_BRACKETS_BYTES = bytearray(_CLOSING_BRACKETS.encode())


def dot_bracket_from_structure(nucleic_acid_strand, scoring=None):
    """
    Represent a nucleic-acid-strand in dot-bracket-letter-notation
    (DBL-notation) [1]_.

    Parameters
    ----------
    atom_array : AtomArray
        The nucleic-acid-strand to be represented in DBL-notation.
    scoring : ndarray, dtype=int, shape=(n,) (default: None)
        The score for each basepair, which is passed on to
        :func:`pseudoknots()`

    Returns
    -------
    notations : list [str, ...]
        The DBL-notation for each solution from :func:`pseudoknots()`.

    See Also
    --------
    base_pairs
    pseudoknots

    References
    ----------

    .. [1] M Antczak, M Popenda and T Zok et al.,
       "New algorithms to represent complex pseudoknotted RNA structures
        in dot-bracket notation.",
       Bioinformatics, 34(8), 1304-1312 (2018).
    """
    basepairs = base_pairs(nucleic_acid_strand)
    basepairs = get_residue_positions(nucleic_acid_strand, basepairs)
    length = get_residue_count(nucleic_acid_strand)
    return dot_bracket(basepairs, length, scoring=scoring)

def dot_bracket(basepairs, length, scoring=None):
    """
    Represent a nucleic-acid-strand in dot-bracket-letter-notation
    (DBL-notation) [1]_.

    The nucleic acid strand is represented as nucleotide sequence,
    where the nucleotides are counted continiously from zero.

    Parameters
    ----------
    basepairs : ndarray, shape=(n,2)
        Each row corresponds to the positions of the bases in the
        strand.
    length : int
        The number of bases in the strand.
    scoring : ndarray, dtype=int, shape=(n,) (default: None)
        The score for each basepair, which is passed on to
        :func:`pseudoknots()`

    Returns
    -------
    notations : list [str, ...]
        The DBL-notation for each solution from :func:`pseudoknots()`.

    Examples
    --------
    The sequence ``ACGTC`` has a length of 5. If there was to be a
    pairing interaction between the ``A`` and ``T``, ``basepairs`` would
    have the form:

    >>> import numpy as np
    >>> basepairs = np.array([[0, 3]])

    The DBL Notation can then be found with ``dot_bracket()``:

    >>> dot_bracket(basepairs, 5)[0]
    '(..).'


    See Also
    --------
    dot_bracket_from_structure
    base_pairs
    pseudoknots

    References
    ----------

    .. [1] M Antczak, M Popenda and T Zok et al.,
       "New algorithms to represent complex pseudoknotted RNA structures
        in dot-bracket notation.",
       Bioinformatics, 34(8), 1304-1312 (2018).
    """
    pseudoknot_order = pseudoknots(basepairs, scoring=scoring)

    # Each optimal pseudoknot order solution is represented in
    # dot-bracket-notation
    notations = [
        bytearray(("."*length).encode()) for _ in range(len(pseudoknot_order))
    ]
    for s, solution in enumerate(pseudoknot_order):
        for basepair, order in zip(basepairs, solution):
            notations[s][basepair[0]] = _OPENING_BRACKETS_BYTES[order]
            notations[s][basepair[1]] = _CLOSING_BRACKETS_BYTES[order]
    return [notation.decode() for notation in notations]

def base_pairs_from_dot_bracket(dot_bracket_notation):
    """
    Extract the basepairs from a nucleic-acid-strand in
    dot-bracket-letter-notation (DBL-notation) [1]_.

    The nucleic acid strand is represented as nucleotide sequence,
    where the nucleotides are counted continiously from zero.

    Parameters
    ----------
    dot_bracket_notation : str
        The DBL-notation.

    Returns
    -------
    basepairs : ndarray, shape=(n,2)
        Each row corresponds to the positions of the bases in the

    Examples
    --------
    The notation string ``'(..).'`` contains a basepair between the
    indices 0 and 3. This pairing interaction can be extracted
    conveniently by the use of :func:`base_pairs_from_dot_bracket()`:

    >>> base_pairs_from_dot_bracket('(..).')
    array([[0, 3]])

    See Also
    --------
    dot_bracket

    References
    ----------

    .. [1] M Antczak, M Popenda and T Zok et al.,
       "New algorithms to represent complex pseudoknotted RNA structures
        in dot-bracket notation.",
       Bioinformatics, 34(8), 1304-1312 (2018).
    """
    basepairs = []
    opened_brackets = {}

    # Iterate through input string and extract base pairs
    for pos, symbol in enumerate(dot_bracket_notation):

        if symbol in _OPENING_BRACKETS:
            # Add opening residues to list (separate list for each
            # bracket type)
            index = _OPENING_BRACKETS.index(symbol)
            if index not in opened_brackets:
                opened_brackets[index] = []
            opened_brackets[index].append(pos)

        elif symbol in _CLOSING_BRACKETS:
            # For each closing bracket, the the basepair consists out of
            # the current index and the last index added to the list in
            # `opened_brackets` corresponding to the same bracket type.
            index = _CLOSING_BRACKETS.index(symbol)
            basepairs.append((opened_brackets[index].pop(), pos))

        else:
            if symbol != ".":
                raise ValueError(
                    f"'{symbol}' is an invalid character for DBL-notation."
                )

    for _, not_closed in opened_brackets.items():
        if not_closed != []:
            raise ValueError(
                "Invalid DBL-notation! Not all opening brackets have a "
                "closing bracket."
            )


    # Sort the base pair indices in ascending order
    basepairs = np.array(basepairs)
    basepairs = basepairs[np.argsort(basepairs[:, 0])]
    return basepairs
