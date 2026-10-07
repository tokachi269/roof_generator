# SPDX-License-Identifier: GPL-3.0-or-later
"""Roof Generator addon. Core imports also work outside Blender."""

bl_info = {
    "name": "Roof Generator",
    "author": "tokachi269",
    "version": (1, 1, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > Roof",
    "description": "Convert a planar footprint to an editable connected roof mesh",
    "category": "Object",
    "doc_url": "https://github.com/tokachi269/roof_generator",
}


def register():
    from . import ui

    ui.register()


def unregister():
    from . import ui

    ui.unregister()
