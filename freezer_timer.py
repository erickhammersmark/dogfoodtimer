import time
from adafruit_circuitplayground import cp

class TimerCommon(object):
    state_change_interval_ms = 60000
    colors = { "green": (0, 255, 0), "yellow": (255, 128, 0), "red": (255, 0, 0), "off": (0, 0, 0) }
    debug = False

    def now(self):
        return int(time.monotonic() * 1000)

    def db(self, msg):
        if self.debug:
            print(msg)

class Lid(TimerCommon):
    RAISED = 1
    LOWERED = 2

    def __init__(self):
        self.state = None
        self.pending_state = None
        self.pending_time = None
        self.debounce_threshold_ms = 100
        self.new_state = None

    def update_state(self):
        x, y, z = [abs(g) for g in cp.acceleration]
        raised = z < 4 and x + y > 4
        lowered = z >= 4 and x + y <= 4
        cur = None
        if raised:
            cur = self.RAISED
        elif lowered:
            cur = self.LOWERED
        else:
            return
        if cur == self.state:
            self.pending_state = None
            self.pending_time = None
        elif cur == self.pending_state:
            if self.now() - self.pending_time >= self.debounce_threshold_ms:
                self.state = self.pending_state
                self.pending_state = None
                self.pending_time = None
                self.new_state = self.state
        else:
            self.pending_state = cur
            self.pending_time = self.now()


    @property
    def raised(self):
        return self.state == self.RAISED

    @property
    def lowered(self):
        return self.state == self.LOWERED

    def __call__(self, trigger=RAISED):
        self.update_state()
        _ns = self.new_state
        self.new_state = None
        return _ns == trigger


class Alarm(TimerCommon):
    visible_alarm_interval_ms = 1000

    audible_alarm_interval_max_ms = 3600 * 1000
    audible_alarm_interval_min_ms = 60 * 1000

    def __init__(self, timer):
        self.timer = timer
        self.reset()

    def reset(self):
        self.alarm_state = False
        self.led_state = False
        self.next_visible_alarm_time_ms = 0
        self.next_audible_alarm_time_ms = 0
        self.audible_alarm_interval_ms = self.audible_alarm_interval_max_ms

    def trigger(self):
        self.alarm_state = True
        self.led_state = True
        self.next_visible_alarm_time_ms = self.now()
        self.next_audible_alarm_time_ms = self.now()

    def update_beep(self):
        if not self.alarm_state:
            return
        if self.now() >= self.next_audible_alarm_time_ms:
            self.next_audible_alarm_time_ms += self.audible_alarm_interval_ms
            cp.play_tone(1760, 2)
            time.sleep(1)
            cp.play_tone(1760, 2)

    def update_lights(self):
        if self.now() >= self.next_visible_alarm_time_ms:
            self.next_visible_alarm_time_ms += self.visible_alarm_interval_ms
            self.led_state = not self.led_state
            if self.led_state:
                timer.set_color("red")
            else:
                timer.set_color("off")

    def __call__(self, alarm_state=True):
        if alarm_state and not self.alarm_state:
            self.trigger()

        self.alarm_state = alarm_state

        if not self.alarm_state:
            self.reset()
            return

        self.update_beep()
        self.update_lights()


class Timer(TimerCommon):
    def __init__(self):
        self.color = None
        self.post()
        self.lid = Lid()
        self.alarm = Alarm(self)
        self.history = []
        self.last_raised_time = self.now()

        self.green_threshold_ms   = 0
        self.yellow_threshold_ms  = self.state_change_interval_ms
        self.red_threshold_ms     = self.state_change_interval_ms * 2
        self.alarm_threshold_ms   = self.state_change_interval_ms * 3


        self.prev_presses = set()

    def set_color(self, color):
        if color in self.colors:
            color = self.colors[color]
        if color == self.color:
            return
        self.color = color
        cp.pixels.fill(color)

    def post(self):
        for color in self.colors:
            self.set_color(color)
            time.sleep(0.5)
        self.set_color("off")

    def buttonx(self, button):
        return getattr(cp, "button_{}".format(button))

    def update_lights(self):
        if self.lid.lowered:
            self.set_color("off")
        else:
            delta = self.now() - self.last_raised_time
            if delta > self.alarm_threshold_ms:
                self.alarm()
            elif delta > self.red_threshold_ms:
                self.set_color("red")
            elif delta > self.yellow_threshold_ms:
                self.set_color("yellow")
            else:
                self.set_color("green")

    def handle_buttons(self):
        presses = set(filter(self.buttonx, ["a", "b"]))
        new_presses = presses - self.prev_presses
        self.prev_presses = presses
        for button in new_presses:
            if button == "a":
                self.snooze()
            elif button == "b":
                self.snooze()

    def __call__(self):
        self.lid.update_state()
        if self.lid.lowered:
            self.alarm(alarm_state=False)
            self.set_color("off")
            return
        elif self.lid():
            self.last_raised_time = self.now()

        self.update_lights()
        self.handle_buttons()

timer = Timer()
while True:
    timer()
