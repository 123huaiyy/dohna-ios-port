/* Copyright (C) 2026 kichikuou <KichikuouChrome@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, see <http://gnu.org/licenses/>.
 */

#include <limits.h>
#include <zlib.h>
#include "system4/zlib.h"

bool zlib_decompress(void *dst, size_t dst_capacity, const void *src, size_t src_len,
		size_t *actual_len_out)
{
	if (dst_capacity > ULONG_MAX || src_len > ULONG_MAX)
		return false;
	uLongf actual_len = (uLongf)dst_capacity;
	if (uncompress((Bytef *)dst, &actual_len, (const Bytef *)src, (uLong)src_len) != Z_OK)
		return false;
	if (actual_len_out)
		*actual_len_out = (size_t)actual_len;
	return true;
}

size_t zlib_compress(void *dst, size_t dst_len, const void *src, size_t src_len, int compression_level)
{
	if (dst_len > ULONG_MAX || src_len > ULONG_MAX)
		return 0;
	uLongf len = (uLongf)dst_len;
	if (compress2((Bytef *)dst, &len, (const Bytef *)src, (uLong)src_len, compression_level) != Z_OK)
		return 0;
	return (size_t)len;
}

size_t zlib_compress_bound(size_t src_len)
{
	if (src_len > ULONG_MAX)
		return 0;
	return (size_t)compressBound((uLong)src_len);
}

bool zlib_decompress_exact(void *dst, size_t dst_len, const void *src, size_t src_len)
{
	size_t actual_len = 0;
	return zlib_decompress(dst, dst_len, src, src_len, &actual_len)
		&& actual_len == dst_len;
}
