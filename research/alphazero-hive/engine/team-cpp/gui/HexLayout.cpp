#include "HexLayout.h"

#include <cmath>

HexLayout::HexLayout(float size, sf::Vector2f origin)
    : HexLayout({1.5f * size, std::sqrt(3.f) * 0.5f * size}, {0.f, std::sqrt(3.f) * size}, size, origin)
{
}

HexLayout::HexLayout(sf::Vector2f qStep, sf::Vector2f rStep, float size, sf::Vector2f origin)
    : size_(size), origin_(origin), qStep_(qStep), rStep_(rStep)
{
}

float HexLayout::size() const
{
    return size_;
}

sf::Vector2f HexLayout::hexToPixel(const Hex &hex) const
{
    const float q = static_cast<float>(hex.q);
    const float r = static_cast<float>(hex.r);
    const float x = qStep_.x * q + rStep_.x * r;
    const float y = qStep_.y * q + rStep_.y * r;
    return {origin_.x + x, origin_.y + y};
}

Hex HexLayout::pixelToHex(sf::Vector2f p) const
{
    const float x = p.x - origin_.x;
    const float y = p.y - origin_.y;

    const float det = qStep_.x * rStep_.y - qStep_.y * rStep_.x;
    const float qf = (x * rStep_.y - y * rStep_.x) / det;
    const float rf = (qStep_.x * y - qStep_.y * x) / det;
    const float cubeS = -qf - rf; // cube coordinate s = -q-r

    float q = std::round(qf);
    float r = std::round(rf);
    float s = std::round(cubeS);

    const float qDiff = std::abs(q - qf);
    const float rDiff = std::abs(r - rf);
    const float sDiff = std::abs(s - cubeS);

    if (qDiff > rDiff && qDiff > sDiff)
    {
        q = -r - s;
    }
    else if (rDiff > sDiff)
    {
        r = -q - s;
    }
    // else: s rounded furthest, but s isn't part of an axial Hex --
    // dropping it is exactly the fix-up, no further assignment needed.

    return Hex{static_cast<int>(q), static_cast<int>(r)};
}
