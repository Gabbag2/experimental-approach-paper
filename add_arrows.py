from expyriment import design, control, stimuli
from expyriment.misc.constants import C_WHITE, C_BLACK
from expyriment.misc import geometry
import math

exp = design.Experiment(name="Blindspot", background_colour=C_WHITE, foreground_colour=C_BLACK)
control.set_develop_mode()
control.initialize(exp)

def add_arrow(direction='top_left', length=80, width=30, color=C_BLACK):
    
    canvas = stimuli.Canvas(size=(200, 200))
    rectangle = stimuli.Rectangle(size=(length, width), colour=color)
    triangle = stimuli.Shape(
            vertex_list=geometry.vertices_regular_polygon(3, 50),  # 3 côtés, rayon 45
            colour=C_BLACK
    )
    if direction == 'top_right':
        rectangle.rotate(45)
        triangle.position = (length / 2, length / 2)
        triangle.rotate(315)
         
    if direction == 'top_left': #ok
        rectangle.rotate(135)
        triangle.position = (-length / 2, length / 2)
        triangle.rotate(45)
        
    if direction == 'bottom_left': #ok
        rectangle.rotate(225)
        triangle.position = (-length / 2, -length / 2)
        triangle.rotate(135)

    if direction == 'bottom_right': #ok
        rectangle.rotate(315)
        triangle.position = (length / 2, -length / 2)
        triangle.rotate(225)


    return (rectangle, triangle)

control.start(subject_id=1)
arrow_stimulus = add_arrow(direction='top_right', length=100, width=40, color=C_BLACK)
arrow_stimulus[0].present(clear=True, update=False)
arrow_stimulus[1].present(clear=False, update=True)

exp.keyboard.wait()
control.end()