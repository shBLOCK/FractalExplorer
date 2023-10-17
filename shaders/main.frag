#version 400 compatibility
//#extension GL_NV_gpu_shader_fp64 : enable
//#extension GL_NV_gpu_shader5 : enable
//#extension GL_ARB_gpu_shader_fp64 : enable
//#pragma optionNV(fastmath off)
//#pragma optionNV(fastprecision off)

precision highp float;

in vec2 fragCoord;
out vec4 fragColor;

#PY_PRECISION_DEFINE USE_DOUBLE_PRECISION

#ifdef USE_DOUBLE_PRECISION
    #define FLOAT double
    #define VEC2 dvec2
    #define VEC3 dvec3
#else
    #define FLOAT float
    #define VEC2 vec2
    #define VEC3 vec3
#endif

uniform float uAspectRatio;
uniform FLOAT uScale;
uniform VEC2 uTranslation;

uniform sampler2D uLastFrame;
uniform float uOldFramesMixFactor;
uniform int uHashSeed;
uniform double uSwizzleMultiplier;

uniform sampler2D uColorPalette;
uniform float uColorChangeSpeed;
uniform int uIters;
uniform float uEscapeThreshold;

uniform int uSamples;

#ifdef USE_DOUBLE_PRECISION
    FLOAT sinF(FLOAT a) { return FLOAT(sin(float(a))); }
    FLOAT cosF(FLOAT a) { return FLOAT(cos(float(a))); }
    FLOAT tanF(FLOAT a) { return FLOAT(tan(float(a))); }
    FLOAT sinhF(FLOAT a) { return FLOAT(sinh(float(a))); }
    FLOAT coshF(FLOAT a) { return FLOAT(cosh(float(a))); }
    FLOAT expF(FLOAT a) { return FLOAT(exp(float(a))); }
#else
    #define sinF sin
    #define cosF cos
    #define tanF tan
    #define sinhF sinh
    #define coshF cosh
    #define expF exp
#endif

#define cx_one VEC2(1.0, 0.0)
VEC2 cx_mul(VEC2 a, VEC2 b) {
    return VEC2(a.x*b.x - a.y*b.y, a.x*b.y + a.y*b.x);
}
VEC2 cx_sqr(VEC2 a) {
    FLOAT x2 = a.x*a.x;
    FLOAT y2 = a.y*a.y;
    FLOAT xy = a.x*a.y;
    return VEC2(x2 - y2, xy + xy);
}
VEC2 cx_cube(VEC2 a) {
    FLOAT x2 = a.x*a.x;
    FLOAT y2 = a.y*a.y;
    FLOAT d = x2 - y2;
    return VEC2(a.x*(d - y2 - y2), a.y*(x2 + x2 + d));
}
VEC2 cx_div(VEC2 a, VEC2 b) {
    FLOAT denom = 1.0 / (b.x*b.x + b.y*b.y);
    return VEC2(a.x*b.x + a.y*b.y, a.y*b.x - a.x*b.y) * denom;
}
VEC2 cx_sin(VEC2 a) {
    return VEC2(sinF(a.x) * coshF(a.y), cosF(a.x) * sinhF(a.y));
}
VEC2 cx_cos(VEC2 a) {
    return VEC2(cosF(a.x) * coshF(a.y), -sinF(a.x) * sinhF(a.y));
}
//TODO: cx_tan(VEC2 a, VEC2 b)
VEC2 cx_exp(VEC2 a) {
    return expF(a.x) * VEC2(cosF(a.y), sinF(a.y));
}
//TODO: cx_pow(VEC2 a, VEC2 b)
//TODO: cx_log(VEC2 a, VEC2 b)
//TODO: cx_sqrt(VEC2 a)

// ---------- Fractals Begin ---------
VEC2 mandelbrot(VEC2 z, VEC2 c) {
    return cx_sqr(z) + c;
}
VEC2 burning_ship(VEC2 z, VEC2 c) {
    return VEC2(z.x*z.x - z.y*z.y, 2.0*abs(z.x * z.y)) + c;
}
VEC2 feather(VEC2 z, VEC2 c) {
    return cx_div(cx_cube(z), cx_one + z*z) + c;
}
VEC2 sfx(VEC2 z, VEC2 c) {
    return z * dot(z,z) - cx_mul(z, c*c);
}
VEC2 henon(VEC2 z, VEC2 c) {
    return VEC2(1.0 - c.x*z.x*z.x + z.y, c.y * z.x);
}
VEC2 duffing(VEC2 z, VEC2 c) {
    return VEC2(z.y, -c.y*z.x + c.x*z.y - z.y*z.y*z.y);
}
VEC2 ikeda(VEC2 z, VEC2 c) {
    FLOAT t = 0.4 - 6.0/(1.0 + dot(z,z));
    FLOAT st = sinF(t);
    FLOAT ct = cosF(t);
    return VEC2(1.0 + c.x*(z.x*ct - z.y*st), c.y*(z.x*st + z.y*ct));
}
VEC2 chirikov(VEC2 z, VEC2 c) {
    z.y += c.y*sinF(z.x);
    z.x += c.x*z.y;
    return z;
}
VEC2 chirikov_mutate(VEC2 z, VEC2 c) {
    return VEC2(z.x + c.x*z.y, z.y + c.y*sinF(z.x));
}
PY_INSERT_RANDOMLY_GENERATED_FUNCTIONS;
// ---------- Fractals End ---------

bool cx_isclose(VEC2 a, VEC2 b) {
    FLOAT epsX = 1e-4;
    FLOAT epsY = 1e-4;
    return abs(a.x - b.x) < epsX && abs(a.y - b.y) < epsY;
}

#define FLAG_USE_COLOR false
vec3 fractal(VEC2 z, VEC2 c) {
    VEC2 pz = z;
    VEC3 sumz = VEC3(0.0, 0.0, 0.0);
    int it;

//    VEC2 history[3];
//    int hist_write_index = 0;

    for (it = 0; it < uIters; ++it) {
        VEC2 ppz = pz;
        pz = z;

        // FRACTAL_FUNC would be replaced with one of the fractal functions
        z = PY_FRACTAL_FUNC(z, c);

//        for (int hi = 0; hi < history.length(); hi++) {
//            VEC2 h = history[hi];
//            if (cx_isclose(z, h)) { return vec3(0., 1., 0.); }
//        }
//        history[hist_write_index % history.length()] = z;
//        hist_write_index ++;


        if (dot(z, z) > uEscapeThreshold) { break; }
        sumz.x += dot(z - pz, pz - ppz);
        sumz.y += dot(z - pz, z - pz);
        sumz.z += dot(z - ppz, z - ppz);
    }

    if (it != uIters) {
//        float k = 2.3;
//        float sit = it - log2(log2(dot(z,z))/(log2(uEscapeThreshold)))/log2(k);
        float palettePos = float(it) * uColorChangeSpeed;
        vec3 paletteColor = texture(uColorPalette, vec2(palettePos, .5)).rgb;
        return paletteColor * (1.0 - float(FLAG_USE_COLOR)*0.85);
    } else if (FLAG_USE_COLOR) {
        sumz = abs(sumz) / FLOAT(uIters);
        vec3 n1 = sin(vec3(abs(sumz * 5.0))) * 0.45 + 0.5;
        return n1;
    } else {
        return vec3(0.);
    }
}

vec2 hash2(uint n) {
    // integer hash copied from Hugo Elias
	n = (n << 13U) ^ n;
    n = n * (n * n * 15731U + 789221U) + 1376312589U;
    uvec2 k = n * uvec2(n,n*16807U);
    return vec2( k & uvec2(0x7fffffffU))/float(0x7fffffff);
}

void main() {
    vec2 ndr = (fragCoord * 2.) - 1.;
    ndr.y *= -1;
    VEC2 position = VEC2(ndr.x * uAspectRatio, ndr.y) * FLOAT(uScale) + VEC2(uTranslation);

    vec3 color = vec3(0.);
    for (int smp = 0; smp < uSamples; smp++) {
        int seed = int(fragCoord.x * 2000.) + int(fragCoord.y * 1000. * 2000.) + smp * 2000 * 1000 * 1000 + uHashSeed;
        VEC2 swizzle = VEC2(hash2(seed) - vec2(.5)) * FLOAT(uSwizzleMultiplier);
        VEC2 fractPos = position + swizzle;
        //TODO: starting pos is either fractPos or VEC2(0.), should be determained for indivisual fractals (by the user)
        color += fractal(fractPos, fractPos);
    }
    color /= uSamples;

    color = clamp(color, 0., 1.);

    vec3 lastFrameColor = texture(uLastFrame, vec2(fragCoord.x, -fragCoord.y)).rgb;
    color = mix(color, lastFrameColor, uOldFramesMixFactor);

    fragColor = vec4(color, 1.);
}