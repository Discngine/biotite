__all__ = ["compress"]
__name__ = "biotite.structure.io.pdbx"
__author__ = "Patrick Kunzmann"

import itertools
import msgpack
import numpy as np
import biotite.structure.io.pdbx.bcif as bcif
from biotite.structure.io.pdbx.bcif import _encode_numpy as encode_numpy
from biotite.structure.io.pdbx.encoding import (
    ByteArrayEncoding,
    DeltaEncoding,
    FixedPointEncoding,
    IntegerPackingEncoding,
    RunLengthEncoding,
    StringArrayEncoding,
)


def compress(data, float_tolerance=1e-6):
    """
    Try to reduce the size of a *BinaryCIF* file (or block, category, etc.) by testing
    different data encodings for each data array and selecting the one, which results in
    the smallest size.

    Parameters
    ----------
    data : BinaryCIFFile or BinaryCIFBlock or BinaryCIFCategory or BinaryCIFColumn or BinaryCIFData
        The data to compress.

    Returns
    -------
    compressed_file : BinaryCIFFile or BinaryCIFBlock or BinaryCIFCategory or BinaryCIFColumn or BinaryCIFData
        The compressed data with the same type as the input data.
        If no improved compression is found for a :class:`BinaryCIFData` array,
        the input data is kept.
        Hence, the return value is no deep copy of the input data.
    float_tolerance : float, optional
        The relative error that is accepted when compressing floating point numbers.

    Examples
    --------

    >>> from io import BytesIO
    >>> pdbx_file = BinaryCIFFile()
    >>> set_structure(pdbx_file, atom_array_stack)
    >>> # Write uncompressed file
    >>> uncompressed_file = BytesIO()
    >>> pdbx_file.write(uncompressed_file)
    >>> _ = uncompressed_file.seek(0)
    >>> print(f"{len(uncompressed_file.read()) // 1000} KB")
    931 KB
    >>> # Write compressed file
    >>> pdbx_file = compress(pdbx_file)
    >>> compressed_file = BytesIO()
    >>> pdbx_file.write(compressed_file)
    >>> _ = compressed_file.seek(0)
    >>> print(f"{len(compressed_file.read()) // 1000} KB")
    113 KB
    """
    match type(data):
        case bcif.BinaryCIFFile:
            return _compress_file(data, float_tolerance)
        case bcif.BinaryCIFBlock:
            return _compress_block(data, float_tolerance)
        case bcif.BinaryCIFCategory:
            return _compress_category(data, float_tolerance)
        case bcif.BinaryCIFColumn:
            return _compress_column(data, float_tolerance)
        case bcif.BinaryCIFData:
            return _compress_data(data, float_tolerance)
        case _:
            raise TypeError(f"Unsupported type {type(data).__name__}")


def _compress_file(bcif_file, float_tolerance):
    compressed_file = bcif.BinaryCIFFile()
    for block_name, bcif_block in bcif_file.items():
        compressed_block = _compress_block(bcif_block, float_tolerance)
        compressed_file[block_name] = compressed_block
    return compressed_file


def _compress_block(bcif_block, float_tolerance):
    compressed_block = bcif.BinaryCIFBlock()
    for category_name, bcif_category in bcif_block.items():
        compressed_category = _compress_category(bcif_category, float_tolerance)
        compressed_block[category_name] = compressed_category
    return compressed_block


def _compress_category(bcif_category, float_tolerance):
    compressed_category = bcif.BinaryCIFCategory()
    for column_name, bcif_column in bcif_category.items():
        compressed_column = _compress_column(bcif_column, float_tolerance)
        compressed_category[column_name] = compressed_column
    return compressed_category


def _compress_column(bcif_column, float_tolerance):
    data = _compress_data(bcif_column.data, float_tolerance)
    if bcif_column.mask is not None:
        mask = _compress_data(bcif_column.mask, float_tolerance)
    else:
        mask = None
    return bcif.BinaryCIFColumn(data, mask)


def _compress_data(bcif_data, float_tolerance):
    array = bcif_data.array
    if len(array) == 1:
        # No need to compress a single value -> Use default uncompressed encoding
        return bcif.BinaryCIFData(array)

    if np.issubdtype(array.dtype, np.str_):
        # Leave encoding empty for now, as it is explicitly set later
        encoding = StringArrayEncoding(data_encoding=[], offset_encoding=[])
        # Run encode to initialize the data and offset arrays
        indices = encoding.encode(array)
        offsets = np.cumsum([0] + [len(s) for s in encoding.strings])
        encoding.data_encoding, _ = _find_best_integer_compression(indices)
        encoding.offset_encoding, _ = _find_best_integer_compression(offsets)
        return bcif.BinaryCIFData(array, [encoding])

    elif np.issubdtype(array.dtype, np.floating):
        to_integer_encoding = FixedPointEncoding(
            10 ** _get_decimal_places(array, float_tolerance)
        )
        integer_array = to_integer_encoding.encode(array)
        best_encoding, size_compressed = _find_best_integer_compression(integer_array)
        if size_compressed < _data_size_in_file(bcif.BinaryCIFData(array)):
            return bcif.BinaryCIFData(array, [to_integer_encoding] + best_encoding)
        else:
            # The float array is smaller -> encode it directly as bytes
            return bcif.BinaryCIFData(array, [ByteArrayEncoding()])

    elif np.issubdtype(array.dtype, np.integer):
        array = _to_smallest_integer_type(array)
        encodings, _ = _find_best_integer_compression(array)
        return bcif.BinaryCIFData(array, encodings)

    else:
        raise TypeError(f"Unsupported data type {array.dtype}")


def _find_best_integer_compression(array):
    """
    Try different data encodings on an integer array and return the one that results in
    the smallest size.
    """
    # Default is no compression at all
    best_encoding_sequence = [ByteArrayEncoding()]
    smallest_size = _data_size_in_file(
        bcif.BinaryCIFData(array, best_encoding_sequence)
    )
    for (
        use_delta,
        use_run_length,
        packed_byte_count,
    ) in itertools.product([False, True], [False, True], [None, 1, 2]):
        encoding_sequence = []
        if use_delta:
            encoding_sequence.append(DeltaEncoding())
        if use_run_length:
            encoding_sequence.append(RunLengthEncoding())
        if packed_byte_count is not None:
            encoding_sequence.append(IntegerPackingEncoding(packed_byte_count))
        encoding_sequence.append(ByteArrayEncoding())
        size = _data_size_in_file(bcif.BinaryCIFData(array, encoding_sequence))
        if size < smallest_size:
            best_encoding_sequence = encoding_sequence
            smallest_size = size
    return best_encoding_sequence, smallest_size


def _to_smallest_integer_type(array):
    """
    Convert an integer array to the smallest possible integer type, that is still able
    to represent all values in the array.

    Parameters
    ----------
    array : numpy.ndarray
        The array to convert.

    Returns
    -------
    array : numpy.ndarray
        The converted array.
    """
    if array.min() >= 0:
        for dtype in [np.uint8, np.uint16, np.uint32, np.uint64]:
            if np.all(array <= np.iinfo(dtype).max):
                return array.astype(dtype)
    for dtype in [np.int8, np.int16, np.int32, np.int64]:
        if np.all(array >= np.iinfo(dtype).min) and np.all(
            array <= np.iinfo(dtype).max
        ):
            return array.astype(dtype)
    raise ValueError("Array is out of bounds for all integer types")


def _data_size_in_file(data):
    """
    Get the size of a :class:`BinaryCIFData` object, it would have when written into a
    file.

    Parameters
    ----------
    data : BinaryCIFData
        The data array whose size is measured.

    Returns
    -------
    size : int
        The size of the data array in the file in bytes.
    """
    bytes_in_file = msgpack.packb(
        data.serialize(), use_bin_type=True, default=encode_numpy
    )
    return len(bytes_in_file)


def _get_decimal_places(array, tol):
    """
    Get the number of decimal places in a floating point array.

    Parameters
    ----------
    array : numpy.ndarray
        The array to analyze.
    tol : float, optional
        The relative tolerance allowed when the values are cut off after the returned
        number of decimal places.

    Returns
    -------
    decimals : int
        The number of decimal places.
    """
    # Decimals of NaN or infinite values do not make sense
    # and 0 would give NaN when rounding on decimals
    array = array[np.isfinite(array) & (array != 0)]
    for decimals in itertools.count(start=-_order_magnitude(array)):
        error = np.abs(np.round(array, decimals) - array)
        if np.all(error < tol * np.abs(array)):
            return decimals


def _order_magnitude(array):
    """
    Get the order of magnitude of floating point values.

    Parameters
    ----------
    array : ndarray, dtype=float
        The value to analyze.

    Returns
    -------
    magnitude : int
        The order of magnitude, i.e. the maximum exponent a number in the array would
        have in scientific notation, if only one digit is left of the decimal point.
    """
    array = array[array != 0]
    if len(array) == 0:
        # No non-zero values -> define order of magnitude as 0
        return 0
    return int(np.max(np.floor(np.log10(np.abs(array)))).item())