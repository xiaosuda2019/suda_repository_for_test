"""通用文本工具函数集合。

本模块提供三个与文本处理相关的纯函数工具：

- :func:`slugify`：把任意文本转换为适合用作 URL、文件名或锚点的 slug。
- :func:`truncate`：按最大长度安全地截断文本，并可选地追加省略号。
- :func:`chunk`：把序列切分为固定大小的多个小块。

所有函数均为无副作用（或仅对入参副本操作）的纯函数，不依赖第三方库，
可直接在 Python 3.8 及以上版本中使用。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, List, Sequence, TypeVar

__all__ = ["slugify", "truncate", "chunk"]

T = TypeVar("T")

# 内部占位记号，用于统一表示分隔符边界后再做折叠。
# 选用私有区码点，正常文本中不会出现，因此不会与输入内容冲突。
_SEPARATOR_TOKEN = "\ue000"

# 匹配一个或多个「非字母、非数字、非空白」的字符，用于替换为分隔符。
_SLUG_SEPARATOR_RE = re.compile(r"[^\w\s-]", re.UNICODE)
# 匹配一个或多个连续的空白字符，用于折叠为单个分隔符。
_SLUG_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)
# 折叠「相邻占位记号 + 空白」的任意组合。
_SLUG_COLLAPSE_RE = re.compile(rf"(?:{_SEPARATOR_TOKEN}|\s)+", re.UNICODE)

# 「组合用记号」（音调符号等）在 NFKD 分解后会单独成为字符，
# 需要在转换前删除，例如 é -> e，否则会残留成多余的分隔符。
_COMBINING_MARKS = {
    codepoint: None
    for codepoint in range(0x110000)
    if unicodedata.category(chr(codepoint)) in ("Mn", "Mc", "Me")
}


def _strip_separator(text: str, separator: str, *, both_ends: bool) -> str:
    """删除文本首尾的空白与分隔符，返回新的字符串。

    使用 ``str.strip`` 会把参数当成「字符集合」，对 ``"."`` 或 ``".-"``
    这类多字符分隔符会误删单个字符，因此这里按完整分隔符逐次剔除。

    Args:
        text: 待处理的文本。
        separator: 需要剔除的分隔符，可以为空字符串。
        both_ends: 为 ``True`` 时同时剔除首尾，为 ``False`` 时只剔除尾部。

    Returns:
        剔除首尾空白和分隔符后的新字符串。
    """
    result = text.strip()
    if not separator:
        return result

    if both_ends:
        while result.startswith(separator):
            result = result[len(separator) :].strip()
    while result.endswith(separator):
        result = result[: -len(separator)].strip()
    return result


def slugify(text: str, separator: str = "-", max_length: int | None = None) -> str:
    """将文本转换为 URL 友好的 slug 字符串。

    转换规则依次为：先做 Unicode 规范化（NFKD）并剔除组合用记号，
    再把所有非字母、非数字、非空白的字符替换为分隔符，随后把连续的分隔符
    与空白折叠成一个分隔符，最后统一转为小写并去除首尾多余的分隔符。
    因此 ``"Hello, World!"`` 会得到 ``"hello-world"``，而
    ``"  Café  au   lait  "`` 会得到 ``"cafe-au-lait"``。

    中文等非 ASCII 字母属于 Unicode 字母，会被保留而不是被丢弃，
    所以 ``"Привет мир"`` 会得到 ``"привет-мир"``；组合用记号会被删除，
    因此 ``"Café"`` 变成 ``"cafe"``。在需要纯 ASCII slug 时请自行先做音译
    或替换处理。

    Args:
        text: 待转换的原始文本。传入 ``None`` 或空字符串时返回空串。
        separator: 用于连接词与词的分隔符，默认为连字符 ``"-"``，
            可以是任意长度的字符串。若传入空字符串，则直接删除被替换的
            字符而不插入任何分隔符。
        max_length: 结果的最大长度限制。为 ``None``（默认）时不限制长度；
            若截断恰好落在分隔符上，会同时去掉尾部的分隔符，
            以保证返回值不会以分隔符结尾。

    Returns:
        规范化后的 slug 字符串。当输入为空或全部字符都被过滤掉时，返回空字符串。

    Raises:
        ValueError: 当 ``max_length`` 为负数时抛出。

    Examples:
        >>> slugify("Hello, World!")
        'hello-world'
        >>> slugify("Café au lait", separator="_")
        'cafe_au_lait'
        >>> slugify("a" * 20, max_length=5)
        'aaaaa'
    """
    if max_length is not None and max_length < 0:
        raise ValueError("max_length 不能为负数")

    if not text:
        return ""

    # 先做兼容分解：é 会变成 e 加一个组合用记号，再把记号删除得到 e；
    # 中文、俄文等本身就是完整字母的字符会被原样保留。
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.translate(_COMBINING_MARKS)

    # 非字母数字的可见字符统一变成占位记号。
    # 之所以不直接替换成分隔符：当 separator 是 ".-" 这类多字符分隔符时，
    # 正则的交替结构只能逐字符匹配，无法整体折叠，故先用单字符占位。
    slug = _SLUG_SEPARATOR_RE.sub(_SEPARATOR_TOKEN, normalized)
    if separator:
        # 连字符同时也是分隔符的组成部分，统一转成占位记号，
        # 否则 "--" 会残留下来（例如 separator=".-" 时）。
        if "-" in separator:
            slug = slug.replace("-", _SEPARATOR_TOKEN)
        # 折叠「相邻占位记号 + 空白」的任意组合，避免出现 "a---b"、
        # "cafe__au_lait" 或 "a.-.-.-b"。
        slug = _SLUG_COLLAPSE_RE.sub(_SEPARATOR_TOKEN, slug)
        slug = slug.replace(_SEPARATOR_TOKEN, separator)
    else:
        # 分隔符为空表示直接删除被替换的字符与空白，而不是把它们变成空格。
        slug = _SLUG_WHITESPACE_RE.sub("", slug.replace(_SEPARATOR_TOKEN, ""))
    slug = _strip_separator(slug, separator, both_ends=True).lower()

    if max_length is not None and len(slug) > max_length:
        slug = _strip_separator(slug[:max_length], separator, both_ends=False)

    return slug


def truncate(
    text: str,
    max_length: int,
    suffix: str = "...",
    *,
    word_boundary: bool = False,
) -> str:
    """按最大长度截断文本，并可选地在末尾追加省略标记。

    当 ``text`` 未超过 ``max_length`` 时原样返回，保证幂等；否则在
    ``max_length`` 之内保留尽可能多的内容，并为 ``suffix`` 预留空间，
    使最终结果的长度不会超过 ``max_length``。若 ``suffix`` 本身比
    ``max_length`` 还长，则只返回 ``suffix`` 的前 ``max_length`` 个字符。

    Args:
        text: 待截断的原始文本。``None`` 会按空字符串处理。
        max_length: 结果允许的最大字符数（以 Python 的字符数为准，而非字节数），
            必须为非负整数。
        suffix: 截断后追加的省略标记，默认为 ``"..."``；传入空字符串表示
            不做任何标记，直接在边界处切断。
        word_boundary: 为 ``True`` 时尝试在最近的空白处断开，避免把单词拦腰截断；
            若在允许范围内找不到空白，则退化为按字符截断。该参数为仅关键字参数。

    Returns:
        截断后的字符串，长度满足 ``len(result) <= max_length``。

    Raises:
        ValueError: 当 ``max_length`` 为负数时抛出。

    Examples:
        >>> truncate("Hello, World!", 8)
        'Hello...'
        >>> truncate("Hello, World!", 8, suffix="~")
        'Hello, ~'
        >>> truncate("Hello, Wonderful World!", 12, word_boundary=True)
        'Hello,...'
        >>> truncate("short", 10)
        'short'
    """
    if max_length < 0:
        raise ValueError("max_length 不能为负数")

    if not text:
        return ""

    if len(text) <= max_length:
        return text

    # suffix 比整体上限还长时，只能保留 suffix 的前缀。
    if len(suffix) >= max_length:
        return suffix[:max_length]

    kept_length = max_length - len(suffix)
    kept = text[:kept_length]

    if word_boundary:
        # 只允许在空白处断开，且断开后不能把内容全部丢光。
        boundary = kept.rfind(" ")
        if boundary > 0:
            kept = kept[:boundary]

    return kept.rstrip() + suffix if word_boundary else kept + suffix


def chunk(items: Sequence[T] | Iterable[T], size: int) -> List[List[T]]:
    """把可迭代对象切分为长度固定的小块列表。

    该函数不会修改原始输入，而是返回一个由列表组成的新列表；
    对于字符串、列表、元组等可迭代对象均适用，也可直接消费生成器。
    最后一块可以短于 ``size``，但当输入为空时不返回任何块。

    Args:
        items: 待切分的可迭代对象或序列，例如列表、元组、生成器或字符串。
        size: 每个块的最大元素数量，必须为正整数。

    Returns:
        由若干列表组成的列表，其中每个子列表的长度为 ``size``，
        最后一个子列表的长度可能小于 ``size``。

    Raises:
        ValueError: 当 ``size`` 小于等于 0 时抛出。

    Examples:
        >>> chunk([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
        >>> chunk("abcde", 3)
        [['a', 'b', 'c'], ['d', 'e']]
        >>> chunk([], 3)
        []
    """
    if size <= 0:
        raise ValueError("size 必须为正整数")

    result: List[List[T]] = []
    # 对序列走下标切片，避免不必要的中间拷贝。
    if isinstance(items, Sequence) and not isinstance(items, (str, bytes)):
        for start in range(0, len(items), size):
            result.append(list(items[start : start + size]))
        return result

    batch: List[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            result.append(batch)
            batch = []
    if batch:
        result.append(batch)
    return result
