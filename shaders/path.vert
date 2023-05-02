#version 400 compatibility

uniform float uAspectRatio;
uniform float uScale;
uniform vec2 uTranslation;
uniform vec2 uScreenSize;

in vec2 vPos;

void main() {
    vec2 ndr = (vPos - uTranslation) / uScale;
    ndr.x /= uAspectRatio;
    ndr.y /= -1;
    vec2 pos = (ndr + 1.) / 2. * uScreenSize;

    gl_Position = vec4(pos, 0., 1.);
}
