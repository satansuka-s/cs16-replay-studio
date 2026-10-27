// Bit reader compatible with GoldSrc MSG_Read* semantics (LSB-first).
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <stdexcept>
#include <string>

namespace gs {

class BitReader {
public:
	BitReader(const uint8_t* data, size_t size, size_t bitPos = 0)
		: data_(data), size_(size), bit_(bitPos) {}

	size_t bitPos() const { return bit_; }
	size_t bitsLeft() const { return size_ * 8 > bit_ ? size_ * 8 - bit_ : 0; }

	bool readBit() {
		if (bit_ >= size_ * 8) { bit_ = size_ * 8; return 0; }
		bool v = (data_[bit_ >> 3] >> (bit_ & 7)) & 1;
		++bit_;
		return v;
	}

	uint32_t readUBits(int n) {
		if (n <= 0) return 0;
		uint32_t v = 0;
		for (int i = 0; i < n; ++i)
			v |= (uint32_t)readBit() << i;
		return v;
	}

	// non-consuming peek
	uint32_t peekUBits(int n) {
		size_t save = bit_;
		uint32_t v = 0;
		for (int i = 0; i < n; ++i) {
			if (bit_ >= size_ * 8) break;
			v |= (uint32_t)((data_[bit_ >> 3] >> (bit_ & 7)) & 1) << i;
			++bit_;
		}
		bit_ = save;
		return v;
	}

	void skip(int n) { for (int i = 0; i < n; ++i) readBit(); }

	int32_t readSBits(int n) {
		uint32_t v = readUBits(n);
		if (n < 32 && (v & (1u << (n - 1))))
			v |= ~((1u << n) - 1);
		return (int32_t)v;
	}

	float readFloat() {
		uint32_t v = readUBits(32);
		float f;
		static_assert(sizeof(float) == sizeof(uint32_t), "float size");
		std::memcpy(&f, &v, 4);
		return f;
	}

	std::string readString(size_t maxLen = 1024) {
		std::string s;
		while (true) {
			uint8_t c = (uint8_t)readUBits(8);
			if (c == 0) break;
			s.push_back((char)c);
			if (s.size() >= maxLen) throw std::runtime_error("string too long");
		}
		return s;
	}

private:
	const uint8_t* data_;
	size_t size_;
	size_t bit_;
};

} // namespace gs
