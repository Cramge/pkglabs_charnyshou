import binascii
import struct
from pathlib import Path

from core.models import ImageMetadata
from .binary import BinaryReader, DamagedFile, UnsupportedFile


FORMAT_EXTENSIONS = {
    "PNG": {".png"},
    "JPEG": {".jpg", ".jpeg", ".jpe"},
    "GIF": {".gif"},
    "TIFF": {".tif", ".tiff"},
    "BMP": {".bmp", ".dib"},
    "PCX": {".pcx"},
}


def _positive(value, label):
    if value is None or value <= 0:
        raise DamagedFile(f"Некорректное значение: {label}")
    return value


def _detect(signature: bytes):
    if signature.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG", _parse_png
    if signature.startswith(b"\xff\xd8\xff"):
        return "JPEG", _parse_jpeg
    if signature.startswith((b"GIF87a", b"GIF89a")):
        return "GIF", _parse_gif
    if signature.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")):
        return "TIFF", _parse_tiff
    if signature.startswith(b"BM"):
        return "BMP", _parse_bmp
    if len(signature) >= 4 and signature[0] == 0x0A and signature[1] in {0, 2, 3, 4, 5}:
        return "PCX", _parse_pcx
    raise UnsupportedFile("Сигнатура не соответствует поддерживаемым форматам")


def parse_image(path: Path) -> ImageMetadata:
    path = Path(path)
    result = ImageMetadata(path=path)
    reader = None
    try:
        reader = BinaryReader(path)
        result.file_size = reader.size
        with reader:
            signature = reader.at(0, min(16, reader.size), "сигнатура") if reader.size else b""
            format_name, parser = _detect(signature)
            result.format_name = format_name
            values = parser(reader)
            for name, value in values.items():
                setattr(result, name, value)
            if path.suffix.lower() not in FORMAT_EXTENSIONS[format_name]:
                result.status = "Предупреждение: расширение не соответствует сигнатуре"
    except UnsupportedFile as error:
        result.status = "Подменённое расширение или неизвестный формат"
        result.details["Причина"] = str(error)
    except DamagedFile as error:
        result.status = "Файл повреждён"
        result.details["Причина"] = str(error)
    except PermissionError:
        result.status = "Ошибка доступа"
        result.details["Причина"] = "Недостаточно прав для чтения файла"
    except OSError as error:
        result.status = "Ошибка доступа"
        result.details["Причина"] = str(error)
    except (OverflowError, ValueError, struct.error) as error:
        result.status = "Файл повреждён"
        result.details["Причина"] = str(error)
    finally:
        if reader is not None:
            result.bytes_read = reader.bytes_read
            result.file_size = reader.size
    return result


def _parse_png(reader: BinaryReader):
    if reader.size < 33:
        raise DamagedFile("PNG короче обязательного заголовка")
    position = 8
    width = height = bit_depth = color_type = None
    dpi_x = dpi_y = None
    interlace = 0
    found_iend = False
    first_chunk = True
    while position + 12 <= reader.size:
        header = reader.at(position, 8, "заголовок чанка PNG")
        length = int.from_bytes(header[:4], "big")
        chunk_type = header[4:]
        reader.ensure(position + 8, length + 4, "данные чанка PNG")
        if first_chunk and chunk_type != b"IHDR":
            raise DamagedFile("Первый чанк PNG не является IHDR")
        if chunk_type == b"IHDR":
            if length != 13 or width is not None:
                raise DamagedFile("Некорректный чанк IHDR")
            data = reader.at(position + 8, 13, "IHDR")
            stored_crc = int.from_bytes(reader.at(position + 21, 4, "CRC IHDR"), "big")
            if binascii.crc32(chunk_type + data) & 0xFFFFFFFF != stored_crc:
                raise DamagedFile("Ошибка CRC чанка IHDR")
            width, height, bit_depth, color_type, compression_method, filter_method, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            _positive(width, "ширина PNG")
            _positive(height, "высота PNG")
            allowed = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
            if color_type not in allowed or bit_depth not in allowed[color_type]:
                raise DamagedFile("Недопустимая комбинация глубины и типа цвета PNG")
            if compression_method != 0 or filter_method != 0 or interlace not in {0, 1}:
                raise DamagedFile("Неизвестный метод PNG")
        elif chunk_type == b"pHYs" and length == 9:
            data = reader.at(position + 8, 9, "pHYs")
            pixels_x, pixels_y, unit = struct.unpack(">IIB", data)
            if unit == 1 and pixels_x and pixels_y:
                dpi_x, dpi_y = pixels_x * 0.0254, pixels_y * 0.0254
        elif chunk_type == b"IEND":
            if length != 0:
                raise DamagedFile("Некорректный чанк IEND")
            data = b""
            stored_crc = int.from_bytes(reader.at(position + 8, 4, "CRC IEND"), "big")
            if binascii.crc32(chunk_type + data) & 0xFFFFFFFF != stored_crc:
                raise DamagedFile("Ошибка CRC чанка IEND")
            found_iend = True
            position += 12
            break
        position += 12 + length
        first_chunk = False
    if width is None or not found_iend:
        raise DamagedFile("Отсутствует IHDR или завершающий IEND")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    if color_type == 3:
        depth = f"{bit_depth} бит (индекс палитры)"
    else:
        depth = f"{bit_depth * channels} бит ({bit_depth} × {channels})"
    details = {
        "Тип цвета": {0: "оттенки серого", 2: "RGB", 3: "палитра", 4: "серый с альфа-каналом", 6: "RGBA"}[color_type],
        "Фильтрация": "адаптивные фильтры PNG, метод 0",
        "Чересстрочность": "Adam7" if interlace else "нет",
    }
    if position < reader.size:
        details["После IEND"] = f"{reader.size - position} байт"
    return {
        "width": width,
        "height": height,
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "color_depth": depth,
        "compression": "Deflate",
        "details": details,
    }


JPEG_SOF = {
    0xC0: "Baseline DCT",
    0xC1: "Extended sequential DCT",
    0xC2: "Progressive DCT",
    0xC3: "Lossless sequential",
    0xC5: "Differential sequential DCT",
    0xC6: "Differential progressive DCT",
    0xC7: "Differential lossless",
    0xC9: "Extended sequential DCT, arithmetic",
    0xCA: "Progressive DCT, arithmetic",
    0xCB: "Lossless, arithmetic",
    0xCD: "Differential sequential, arithmetic",
    0xCE: "Differential progressive, arithmetic",
    0xCF: "Differential lossless, arithmetic",
}


def _parse_jpeg(reader: BinaryReader):
    if reader.size < 4 or reader.at(0, 2, "SOI") != b"\xff\xd8":
        raise DamagedFile("Отсутствует маркер SOI")
    position = 2
    width = height = precision = components = None
    dpi_x = dpi_y = None
    compression = "JPEG"
    while position + 2 <= reader.size:
        first = reader.at(position, 1, "маркер JPEG")[0]
        if first != 0xFF:
            raise DamagedFile("Нарушена последовательность маркеров JPEG")
        while position < reader.size and reader.at(position, 1, "маркер JPEG")[0] == 0xFF:
            position += 1
        if position >= reader.size:
            break
        marker = reader.at(position, 1, "код маркера JPEG")[0]
        marker_start = position - 1
        position += 1
        if marker == 0xD9:
            break
        if marker in {0x01, *range(0xD0, 0xD8)}:
            continue
        if position + 2 > reader.size:
            raise DamagedFile("Обрезана длина сегмента JPEG")
        segment_length = int.from_bytes(reader.at(position, 2, "длина сегмента JPEG"), "big")
        if segment_length < 2:
            raise DamagedFile("Некорректная длина сегмента JPEG")
        data_position = position + 2
        data_length = segment_length - 2
        reader.ensure(data_position, data_length, "сегмент JPEG")
        if marker == 0xE0 and data_length >= 12:
            data = reader.at(data_position, 12, "JFIF")
            if data[:5] == b"JFIF\x00":
                unit = data[7]
                density_x = int.from_bytes(data[8:10], "big")
                density_y = int.from_bytes(data[10:12], "big")
                if density_x and density_y:
                    if unit == 1:
                        dpi_x, dpi_y = float(density_x), float(density_y)
                    elif unit == 2:
                        dpi_x, dpi_y = density_x * 2.54, density_y * 2.54
        if marker in JPEG_SOF:
            if data_length < 6:
                raise DamagedFile("Обрезан сегмент SOF")
            data = reader.at(data_position, 6, "SOF")
            precision = data[0]
            height = int.from_bytes(data[1:3], "big")
            width = int.from_bytes(data[3:5], "big")
            components = data[5]
            _positive(width, "ширина JPEG")
            _positive(height, "высота JPEG")
            _positive(components, "число компонентов JPEG")
            compression = JPEG_SOF[marker]
        position = marker_start + 2 + segment_length
        if marker == 0xDA:
            break
    if reader.size < 2 or reader.at(reader.size - 2, 2, "конец JPEG") != b"\xff\xd9":
        raise DamagedFile("Отсутствует маркер EOI")
    if width is None:
        raise DamagedFile("Не найден сегмент SOF")
    return {
        "width": width,
        "height": height,
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "color_depth": f"{precision * components} бит ({precision} × {components})",
        "compression": compression,
        "details": {"Компонентов": str(components), "Точность компонента": f"{precision} бит"},
    }


def _gif_skip_blocks(reader: BinaryReader, position: int) -> int:
    while True:
        size = reader.at(position, 1, "размер блока GIF")[0]
        position += 1
        if size == 0:
            return position
        reader.ensure(position, size, "данные блока GIF")
        position += size


def _parse_gif(reader: BinaryReader):
    if reader.size < 14:
        raise DamagedFile("GIF короче логического дескриптора")
    header = reader.at(0, 13, "заголовок GIF")
    if header[:6] not in {b"GIF87a", b"GIF89a"}:
        raise DamagedFile("Некорректная сигнатура GIF")
    width, height = struct.unpack_from("<HH", header, 6)
    _positive(width, "ширина GIF")
    _positive(height, "высота GIF")
    packed = header[10]
    global_bits = (packed & 0x07) + 1 if packed & 0x80 else 0
    position = 13 + (3 * (1 << global_bits) if global_bits else 0)
    reader.ensure(0, position, "глобальная палитра GIF")
    max_bits = global_bits
    images = 0
    found_trailer = False
    while position < reader.size:
        introducer = reader.at(position, 1, "блок GIF")[0]
        position += 1
        if introducer == 0x3B:
            found_trailer = True
            break
        if introducer == 0x21:
            reader.ensure(position, 1, "метка расширения GIF")
            position += 1
            position = _gif_skip_blocks(reader, position)
            continue
        if introducer == 0x2C:
            descriptor = reader.at(position, 9, "дескриптор изображения GIF")
            image_width, image_height = struct.unpack_from("<HH", descriptor, 4)
            _positive(image_width, "ширина кадра GIF")
            _positive(image_height, "высота кадра GIF")
            local_packed = descriptor[8]
            local_bits = (local_packed & 0x07) + 1 if local_packed & 0x80 else 0
            max_bits = max(max_bits, local_bits)
            position += 9 + (3 * (1 << local_bits) if local_bits else 0)
            reader.ensure(position, 1, "минимальный код LZW")
            position += 1
            position = _gif_skip_blocks(reader, position)
            images += 1
            continue
        raise DamagedFile("Неизвестный блок GIF")
    if not found_trailer:
        raise DamagedFile("Отсутствует завершающий байт GIF")
    if not images:
        raise DamagedFile("GIF не содержит изображения")
    palette_size = 1 << max_bits if max_bits else 0
    return {
        "width": width,
        "height": height,
        "color_depth": f"{max_bits or 1} бит (палитра)",
        "compression": "LZW",
        "details": {"Кадров": str(images), "Цветов в палитре": str(palette_size)},
    }


BMP_COMPRESSION = {
    0: "BI_RGB (без сжатия)",
    1: "BI_RLE8",
    2: "BI_RLE4",
    3: "BI_BITFIELDS",
    4: "BI_JPEG",
    5: "BI_PNG",
    6: "BI_ALPHABITFIELDS",
    11: "BI_CMYK",
    12: "BI_CMYKRLE8",
    13: "BI_CMYKRLE4",
}


def _parse_bmp(reader: BinaryReader):
    if reader.size < 26:
        raise DamagedFile("BMP короче обязательных заголовков")
    file_header = reader.at(0, 14, "BITMAPFILEHEADER")
    if file_header[:2] != b"BM":
        raise DamagedFile("Некорректная сигнатура BMP")
    declared_size = int.from_bytes(file_header[2:6], "little")
    pixel_offset = int.from_bytes(file_header[10:14], "little")
    dib_size = int.from_bytes(reader.at(14, 4, "размер DIB"), "little")
    if declared_size and declared_size > reader.size:
        raise DamagedFile("Размер файла меньше значения из BITMAPFILEHEADER")
    if dib_size == 12:
        dib = reader.at(14, 12, "BITMAPCOREHEADER")
        width, height, planes, bits = struct.unpack_from("<HHHH", dib, 4)
        compression_code = 0
        image_size = 0
        dpi_x = dpi_y = None
        colors_used = 1 << bits if bits <= 8 else 0
        palette_entry = 3
    elif dib_size >= 40:
        if dib_size > 16 * 1024 * 1024:
            raise DamagedFile("Нереалистичный размер DIB-заголовка")
        dib = reader.at(14, 40, "BITMAPINFOHEADER")
        width, signed_height, planes, bits, compression_code, image_size, ppm_x, ppm_y, colors_used, _ = struct.unpack_from(
            "<iiHHIIiiII", dib, 4
        )
        height = abs(signed_height)
        dpi_x = ppm_x * 0.0254 if ppm_x > 0 else None
        dpi_y = ppm_y * 0.0254 if ppm_y > 0 else None
        if not colors_used and bits <= 8:
            colors_used = 1 << bits
        palette_entry = 4
    else:
        raise DamagedFile(f"Неподдерживаемый DIB-заголовок размером {dib_size}")
    _positive(width, "ширина BMP")
    _positive(height, "высота BMP")
    if planes != 1 or bits not in {1, 2, 4, 8, 16, 24, 32}:
        raise DamagedFile("Некорректное число плоскостей или глубина BMP")
    if compression_code not in BMP_COMPRESSION:
        compression = f"неизвестный код {compression_code}"
    else:
        compression = BMP_COMPRESSION[compression_code]
    header_end = 14 + dib_size
    if pixel_offset < header_end or pixel_offset > reader.size:
        raise DamagedFile("Некорректное смещение массива пикселей BMP")
    if colors_used:
        palette_end = header_end + colors_used * palette_entry
        if palette_end > pixel_offset:
            raise DamagedFile("Палитра BMP выходит за начало массива пикселей")
    if compression_code in {0, 3, 6}:
        expected = ((width * bits + 31) // 32) * 4 * height
        if pixel_offset + expected > reader.size:
            raise DamagedFile("Массив пикселей BMP обрезан")
    elif image_size and pixel_offset + image_size > reader.size:
        raise DamagedFile("Сжатые данные BMP обрезаны")
    details = {"DIB-заголовок": f"{dib_size} байт"}
    if colors_used:
        details["Цветов в палитре"] = str(colors_used)
    return {
        "width": width,
        "height": height,
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "color_depth": f"{bits} бит",
        "compression": compression,
        "details": details,
    }


TIFF_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 16: 8, 17: 8, 18: 8}
TIFF_COMPRESSION = {
    1: "без сжатия",
    2: "CCITT RLE",
    3: "CCITT Group 3",
    4: "CCITT Group 4",
    5: "LZW",
    6: "Old JPEG",
    7: "JPEG",
    8: "Deflate",
    32773: "PackBits",
    32946: "Deflate",
}


def _tiff_values(reader, endian, big_tiff, entry_offset):
    byte_order = "little" if endian == "<" else "big"
    entry_size = 20 if big_tiff else 12
    inline_size = 8 if big_tiff else 4
    entry = reader.at(entry_offset, entry_size, "элемент IFD")
    tag = int.from_bytes(entry[0:2], byte_order)
    type_code = int.from_bytes(entry[2:4], byte_order)
    count_size = 8 if big_tiff else 4
    count = int.from_bytes(entry[4:4 + count_size], byte_order)
    field = entry[4 + count_size:4 + count_size + inline_size]
    if type_code not in TIFF_TYPE_SIZE or count > 1_000_000:
        return tag, type_code, count, []
    total = TIFF_TYPE_SIZE[type_code] * count
    if total > 16 * 1024 * 1024:
        raise DamagedFile("Слишком большой массив значений TIFF-тега")
    if total <= inline_size:
        raw = field[:total]
    else:
        value_offset = int.from_bytes(field, byte_order)
        raw = reader.at(value_offset, total, f"значение TIFF-тега {tag}")
    prefix = endian
    if type_code in {1, 6, 7}:
        return tag, type_code, count, list(raw)
    if type_code == 2:
        return tag, type_code, count, [raw.rstrip(b"\x00").decode("latin1", errors="replace")]
    formats = {3: "H", 4: "I", 8: "h", 9: "i", 11: "f", 12: "d", 16: "Q", 17: "q", 18: "Q"}
    if type_code in formats:
        values = list(struct.unpack(prefix + formats[type_code] * count, raw))
        return tag, type_code, count, values
    if type_code in {5, 10}:
        signed = type_code == 10
        values = []
        for index in range(count):
            part = raw[index * 8:index * 8 + 8]
            numerator = int.from_bytes(part[:4], byte_order, signed=signed)
            denominator = int.from_bytes(part[4:], byte_order, signed=signed)
            values.append(numerator / denominator if denominator else 0.0)
        return tag, type_code, count, values
    return tag, type_code, count, []


def _parse_tiff(reader: BinaryReader):
    if reader.size < 8:
        raise DamagedFile("TIFF короче заголовка")
    order = reader.at(0, 2, "порядок байтов TIFF")
    if order == b"II":
        endian, byte_order = "<", "little"
    elif order == b"MM":
        endian, byte_order = ">", "big"
    else:
        raise DamagedFile("Некорректный порядок байтов TIFF")
    version = int.from_bytes(reader.at(2, 2, "версия TIFF"), byte_order)
    if version == 42:
        big_tiff = False
        first_ifd = int.from_bytes(reader.at(4, 4, "смещение IFD"), byte_order)
    elif version == 43:
        big_tiff = True
        if reader.size < 16:
            raise DamagedFile("BigTIFF короче заголовка")
        offset_size = int.from_bytes(reader.at(4, 2, "размер смещения BigTIFF"), byte_order)
        reserved = int.from_bytes(reader.at(6, 2, "резерв BigTIFF"), byte_order)
        if offset_size != 8 or reserved != 0:
            raise DamagedFile("Некорректный заголовок BigTIFF")
        first_ifd = int.from_bytes(reader.at(8, 8, "смещение IFD BigTIFF"), byte_order)
    else:
        raise DamagedFile("Неизвестная версия TIFF")
    if not first_ifd:
        raise DamagedFile("TIFF не содержит IFD")
    count_size = 8 if big_tiff else 2
    entry_size = 20 if big_tiff else 12
    next_size = 8 if big_tiff else 4
    visited = set()
    pages = []
    ifd_offset = first_ifd
    for _ in range(64):
        if not ifd_offset:
            break
        if ifd_offset in visited:
            raise DamagedFile("Циклическая цепочка IFD")
        visited.add(ifd_offset)
        entry_count = int.from_bytes(reader.at(ifd_offset, count_size, "число элементов IFD"), byte_order)
        if entry_count > 65535:
            raise DamagedFile("Нереалистичное число элементов IFD")
        entries_start = ifd_offset + count_size
        reader.ensure(entries_start, entry_count * entry_size + next_size, "таблица IFD")
        tags = {}
        for index in range(entry_count):
            tag, type_code, count, values = _tiff_values(reader, endian, big_tiff, entries_start + index * entry_size)
            if values:
                tags[tag] = values
        next_offset_position = entries_start + entry_count * entry_size
        ifd_offset = int.from_bytes(reader.at(next_offset_position, next_size, "следующий IFD"), byte_order)
        width = int(tags.get(256, [0])[0])
        height = int(tags.get(257, [0])[0])
        if width and height:
            pages.append(tags)
    if not pages:
        raise DamagedFile("В IFD отсутствуют размеры изображения")
    tags = pages[0]
    width = _positive(int(tags[256][0]), "ширина TIFF")
    height = _positive(int(tags[257][0]), "высота TIFF")
    bits = [int(value) for value in tags.get(258, [1])]
    samples = int(tags.get(277, [len(bits) or 1])[0])
    depth = sum(bits) if len(bits) > 1 else bits[0] * samples
    compression_code = int(tags.get(259, [1])[0])
    compression = TIFF_COMPRESSION.get(compression_code, f"код {compression_code}")
    dpi_x = float(tags.get(282, [0.0])[0]) or None
    dpi_y = float(tags.get(283, [0.0])[0]) or None
    resolution_unit = int(tags.get(296, [2])[0])
    if resolution_unit == 3:
        dpi_x = dpi_x * 2.54 if dpi_x else None
        dpi_y = dpi_y * 2.54 if dpi_y else None
    elif resolution_unit != 2:
        dpi_x = dpi_y = None
    offsets = tags.get(273) or tags.get(324) or []
    byte_counts = tags.get(279) or tags.get(325) or []
    if bool(offsets) != bool(byte_counts):
        raise DamagedFile("Не согласованы смещения и размеры полос TIFF")
    if offsets and len(byte_counts) not in {1, len(offsets)}:
        raise DamagedFile("Не совпадает число полос TIFF")
    if len(byte_counts) == 1 and len(offsets) > 1:
        byte_counts = byte_counts * len(offsets)
    for offset, count in zip(offsets, byte_counts):
        reader.ensure(int(offset), int(count), "полоса или тайл TIFF")
    details = {
        "Порядок байтов": "little-endian" if endian == "<" else "big-endian",
        "Страниц IFD": str(len(pages)),
        "Компонентов": str(samples),
    }
    if 320 in tags:
        details["Цветов в палитре"] = str(len(tags[320]) // 3)
    return {
        "width": width,
        "height": height,
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
        "color_depth": f"{depth} бит ({' + '.join(map(str, bits))})",
        "compression": compression,
        "details": details,
    }


def _pcx_validate_rle(reader: BinaryReader, start: int, end: int, expected: int):
    reader.seek(start)
    produced = 0
    carry = None
    while reader.tell() < end and produced < expected:
        chunk = reader.read(min(65536, end - reader.tell()))
        if not chunk:
            break
        index = 0
        if carry is not None:
            produced += carry
            carry = None
            index = 1
        while index < len(chunk) and produced < expected:
            value = chunk[index]
            index += 1
            if value & 0xC0 == 0xC0:
                count = value & 0x3F
                if index >= len(chunk):
                    carry = count
                    break
                index += 1
                produced += count
            else:
                produced += 1
        if produced > expected:
            raise DamagedFile("RLE-поток PCX содержит лишние данные строки")
    if carry is not None or produced < expected:
        raise DamagedFile("RLE-поток PCX обрезан")


def _parse_pcx(reader: BinaryReader):
    if reader.size < 128:
        raise DamagedFile("PCX короче 128-байтового заголовка")
    header = reader.at(0, 128, "заголовок PCX")
    manufacturer, version, encoding, bits_per_plane = header[:4]
    if manufacturer != 0x0A or version not in {0, 2, 3, 4, 5} or encoding not in {0, 1}:
        raise DamagedFile("Некорректный заголовок PCX")
    x_min, y_min, x_max, y_max, h_dpi, v_dpi = struct.unpack_from("<HHHHHH", header, 4)
    width = x_max - x_min + 1
    height = y_max - y_min + 1
    _positive(width, "ширина PCX")
    _positive(height, "высота PCX")
    planes = header[65]
    bytes_per_line = int.from_bytes(header[66:68], "little")
    if not planes or bits_per_plane not in {1, 2, 4, 8}:
        raise DamagedFile("Некорректная глубина PCX")
    minimum_line = (width * bits_per_plane + 7) // 8
    if bytes_per_line < minimum_line:
        raise DamagedFile("Строка PCX короче ширины изображения")
    data_end = reader.size
    palette_colors = 16 if bits_per_plane * planes <= 4 else 0
    if bits_per_plane == 8 and planes == 1 and reader.size >= 897:
        palette = reader.at(reader.size - 769, 769, "палитра PCX")
        if palette[0] == 0x0C:
            data_end -= 769
            palette_colors = 256
    expected = bytes_per_line * planes * height
    if encoding == 0:
        if data_end - 128 < expected:
            raise DamagedFile("Пиксельные данные PCX обрезаны")
    else:
        _pcx_validate_rle(reader, 128, data_end, expected)
    return {
        "width": width,
        "height": height,
        "dpi_x": float(h_dpi) if h_dpi else None,
        "dpi_y": float(v_dpi) if v_dpi else None,
        "color_depth": f"{bits_per_plane * planes} бит ({bits_per_plane} × {planes})",
        "compression": "PCX RLE" if encoding == 1 else "без сжатия",
        "details": {"Цветов в палитре": str(palette_colors), "Байт на строку и плоскость": str(bytes_per_line)},
    }

