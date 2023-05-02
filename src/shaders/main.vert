#version 400 compatibility

in vec2 vert;
in vec2 texCoord;
out vec2 fragCoord;

void main() {
    fragCoord = texCoord;

    gl_Position = vec4(vert, 0., 1.);
}