from typing import Generic, TypeVar, Tuple, List


T = TypeVar('T')

class Node(Generic[T]):
    def __init__(self, inputs:List, parameters:List=[]):
        self.input:List = inputs
        self.parameters = parameters

    def process(self, request)->T:
    	...


from dataclasses import dataclass


@dataclass
class VideoFrameRequest:
    frame:int
    roi: Tuple[int, int, int, int]


type ImageRGBA = np.ndarray
class Read(Node[ImageRGBA]):
	def __init__(self, path:str):
		self.path = path

	def process(self, request:VideoFrameRequest)->ImageRGBA:
		frame = request
		return imageio.read(self.path % frame)


class TimeOffset(Node[ImageRGBA]):
    def __init__(self, source, offset:int):
    	self.source = source
    	self.offset = ...

    def process(self, request:VideoFrameRequest):
        self.source.process(request)
