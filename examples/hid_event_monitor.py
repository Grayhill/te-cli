from te.interface.guide import GuideGestureType
from te.utils.discovery_tool import discover_touch_encoders
from te.interface.hid import HIDTouchEncoder
from te.interface.hid import hid_reports

class GuideTouchEventReport(hid_reports.GuideTouchEventReport):
    def __str__(self):
        return f'''
        Guide Touch Event
        Element ID: {self.element_id}
        Touch Type: {self.touch_type.name}
        X: {self.x}
        Y: {self.y}
        '''

class GuideGestureEventReport(hid_reports.GuideGestureEventReport):
    def __str__(self):
        base_str = f'''
        Guide Gesture Event
        Element ID: {self.element_id}
        Gesture Type: {self.gesture_type.name}
        '''
        if self.gesture_type == GuideGestureType.TAP:
            return f'{base_str}X: {self.x}\nY: {self.y}\n'
        return f'{base_str}Direction: {self.direction.name}\n'

class GuideKnobEventReport(hid_reports.GuideKnobEventReport):
    def __str__(self):
        return f'''
        Guide Knob Event
        Element ID: {self.element_id}
        Relative Value: {self.relative_value}
        '''

# Discover connected devices
devices = discover_touch_encoders()

# Exit if no devices found
if len(devices) == 0:
    print('No devices found')
    exit()

# Find the first HID device
dev = next((_dev for _dev in devices if isinstance(_dev, HIDTouchEncoder)), None)

# Monitor events for taps, gestures, encoder rotation, etc.
while True:
    # Wait for an event, timeout after 1 second
    res = dev.await_res(expected_res=[
        hid_reports.GuideTouchEventReport,
        hid_reports.GuideGestureEventReport,
        hid_reports.GuideKnobEventReport,
    ], timeout=1.0)

    if res:
        print(str(res))