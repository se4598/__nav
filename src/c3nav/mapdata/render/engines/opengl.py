import io
from collections import deque
from itertools import chain
from typing import Optional, Union

import ModernGL
import numpy as np
from PIL import Image
from shapely.geometry import CAP_STYLE, JOIN_STYLE, MultiPolygon, Polygon
from shapely.ops import unary_union

from c3nav.mapdata.render.engines.base import FillAttribs, RenderEngine, StrokeAttribs
from c3nav.mapdata.utils.mesh import triangulate_polygon


class OpenGLEngine(RenderEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.vertices = []
        self.ctx = ModernGL.create_standalone_context()

        self.color_rbo = self.ctx.renderbuffer((self.width, self.height))
        self.fbo = self.ctx.framebuffer([self.color_rbo])
        self.fbo.use()

        self.ctx.clear(*(i/255 for i in self.background_rgb))

        self.prog = self.ctx.program([
            self.ctx.vertex_shader('''
                #version 330
                in vec2 in_vert;
                in vec4 in_color;
                out vec4 v_color;
                void main() {
                    gl_Position = vec4(in_vert, 0.0, 1.0);
                    v_color = in_color;
                }
            '''),
            self.ctx.fragment_shader('''
                #version 330
                in vec4 v_color;
                out vec4 f_color;
                void main() {
                    f_color = v_color;
                }
            '''),
        ])

        scale_x = self.scale / self.width * 2
        scale_y = self.scale / self.height * 2

        self.np_scale = np.array((scale_x, -scale_y))
        self.np_offset = np.array((-self.minx * scale_x - 1, self.maxy * scale_y - 1))

    def _create_geometry(self, geometry: Union[Polygon, MultiPolygon], append=None):
        triangles = deque()

        vertices, faces = triangulate_polygon(geometry)
        triangles = vertices[faces.flatten()]

        vertices = np.vstack(triangles).astype(np.float32)
        vertices = vertices * self.np_scale + self.np_offset
        if append is not None:
            append = np.array(append, dtype=np.float32).flatten()
            vertices = np.hstack((
                vertices,
                append.reshape(1, append.size).repeat(vertices.shape[0], 0)
            ))
        return vertices.flatten()

    def _add_geometry(self, geometry, fill: Optional[FillAttribs] = None, stroke: Optional[StrokeAttribs] = None,
                      altitude=None, height=None, shape_cache_key=None):
        if fill is not None:
            if stroke is not None and fill.color == stroke.color:
                geometry = geometry.buffer(max(stroke.width, (stroke.min_px or 0) / self.scale),
                                           cap_style=CAP_STYLE.flat, join_style=JOIN_STYLE.mitre)
                stroke = None
            self.vertices.append(self._create_geometry(geometry, self.color_to_rgb(fill.color)))

        if stroke is not None:
            lines = tuple(chain(*(
                ((geom.exterior, *geom.interiors) if isinstance(geom, Polygon) else (geom, ))
                for geom in getattr(geometry, 'geoms', (geometry, ))
            )))
            one_pixel = 1 / self.scale / 2
            width = max(stroke.width, (stroke.min_px or 0) / self.scale) / 2
            if width < one_pixel:
                alpha = width/one_pixel
                width = one_pixel
            else:
                alpha = 1
            self.vertices.append(self._create_geometry(
                unary_union(lines).buffer(width, cap_style=CAP_STYLE.flat, join_style=JOIN_STYLE.mitre),
                self.color_to_rgb(stroke.color, alpha=alpha)
            ))

    def get_png(self) -> bytes:
        if self.vertices:
            vbo = self.ctx.buffer(np.hstack(self.vertices).astype(np.float32).tobytes())

            # We control the 'in_vert' and `in_color' variables
            vao = self.ctx.simple_vertex_array(self.prog, vbo, ['in_vert', 'in_color'])
            vao.render()

        img = Image.frombytes('RGB', (self.width, self.height), self.fbo.read(components=3))

        f = io.BytesIO()
        img.save(f, 'PNG')
        f.seek(0)
        return f.read()
