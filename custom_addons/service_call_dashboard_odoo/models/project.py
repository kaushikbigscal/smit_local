import random
from odoo import models


class Project(models.Model):
    """This class inherits from 'project.project' and adds custom functionality
    to it.It provides methods to work with project data."""
    _inherit = 'project.project'

    def get_color_code(self):
        """Generate a random color code in hexadecimal format.
        :return: A random color code in the format '#RRGGBB.'"""
        color = f"#{random.randint(0, 0xFFFFFF):06x}"
        return color
