import os
import time
from adafruit_circuitplayground import cp


class DogfoodTimerCommon(object):
    colors = { "green": (0, 255, 0), "yellow": (255, 128, 0), "red": (255, 0, 0) }
    debug = False

    def now(self):
        return int(time.monotonic() * 1000)

    def db(self, msg):
        if self.debug:
            print(msg)


class Lid(DogfoodTimerCommon):
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

    def __call__(self):
        self.update_state()
        _ns = self.new_state
        self.new_state = None
        return _ns == self.RAISED


class Alarm(DogfoodTimerCommon):
    visible_alarm_interval_ms = 1000 # flash the LEDs on a 2-second period

#    audible_alarm_interval_max_ms = 30 * 1000 # 10 seconds
#    audible_alarm_interval_min_ms = 5 * 1000 # 10 seconds
    audible_alarm_interval_max_ms = 3600 * 1000 # 1 hour
    audible_alarm_interval_min_ms = 60 * 1000 # 1 minute

    beep_on_time_ms = 600    # the length of one beep (600ms)
    beep_off_time_ms = 1000  # the time between beeps in a set (1 second)
    n_beeps = 3              # the number of beeps in one set

    def __init__(self):
        self.beep_state = False
        self.reset()

    def reset(self):
        self.alarm_state = False
        self.led_state = True
        self.next_visible_alarm_time_ms = 0
        self.next_audible_alarm_time_ms = 0
        self.audible_alarm_interval_ms = self.audible_alarm_interval_max_ms

        self.next_beep_update_time_ms = 0
        self.beep_set(False)
        self.beep_num = 0
        self.actually_beeping = False

    def trigger(self):
        self.alarm_state = True
        self.next_visible_alarm_time_ms = self.now()
        self.next_audible_alarm_time_ms = self.now()

    def beep_set(self, state):
        if state != self.beep_state:
            if state:
                if cp.switch:
                    self.actually_beeping = True
                    cp.start_tone(1760)
            elif self.actually_beeping:
                self.actually_beeping = False
                cp.stop_tone()
            self.beep_state = state

    def update_beep(self):
        if self.now() >= self.next_audible_alarm_time_ms:
            self.next_audible_alarm_time_ms += self.audible_alarm_interval_ms
            self.audible_alarm_interval_ms = max(self.audible_alarm_interval_ms / 2, self.audible_alarm_interval_min_ms)
            self.next_beep_update_time_ms = self.now()
            self.beep_set(False)
            self.beep_num = 0

        if self.next_beep_update_time_ms != 0 and self.now() >= self.next_beep_update_time_ms:
            if self.beep_state:
                self.beep_set(False)
                self.beep_num += 1
                if self.beep_num >= self.n_beeps:
                    self.next_beep_update_time_ms = 0
                    self.beep_num = 0
                    return
                self.next_beep_update_time_ms += self.beep_off_time_ms
            else:
                self.beep_set(True)
                self.next_beep_update_time_ms += self.beep_on_time_ms

    def update_lights(self):
        if self.now() >= self.next_visible_alarm_time_ms:
            self.next_visible_alarm_time_ms += self.visible_alarm_interval_ms
            self.led_state = not self.led_state
            if self.led_state:
                cp.pixels.fill(self.colors["red"])
            else:
                cp.pixels.fill(0)

    def __call__(self, alarm_state=True):
        if alarm_state and not self.alarm_state:
            self.trigger()

        self.alarm_state = alarm_state

        if not self.alarm_state:
            self.reset()
            return

        self.update_beep()
        self.update_lights()


class Timer(DogfoodTimerCommon):
    one_hour_ms          = 3600000
    #one_hour_ms          = 2000
    green_threshold_ms   = 0
    yellow_threshold_ms  = one_hour_ms * 4
    red_threshold_ms     = one_hour_ms * 8
    alarm_threshold_ms   = one_hour_ms * 12

    UNDO_WAV = "undo.wav"
    SNOOZE_WAV = "snooze.wav"

    def __init__(self):
        self.post()
        self.lid = Lid()
        self.alarm = Alarm()
        self.history = []
        self.last_raised_time = self.now()

        self.prev_presses = set()

        for file in [self.UNDO_WAV, self.SNOOZE_WAV]:
            try:
                os.stat(file)
            except Exception as e:
                print("File %s not found!" % (file))

    def post(self):
        '''
        Simple power on self test
        briefly sets the LEDs to each of the colors.
        '''
        for color in ["green", "yellow", "red"]:
            cp.pixels.fill(self.colors[color])
            time.sleep(0.5)
        cp.pixels.fill(0)

    def undo(self, quiet=False):
        self.db("Undo pressed")
        undone_time = None
        if self.history:
            undone_time = self.last_raised_time
            self.last_raised_time = self.history.pop(-1)
            if not quiet:
                try:
                    cp.play_file(self.UNDO_WAV)
                except:
                    pass
        return undone_time

    def record_time(self, raised_time=None):
        raised_time = raised_time or self.now()
        self.history.append(self.last_raised_time)
        self.history = self.history[-10:]
        self.last_raised_time = raised_time

    def snooze(self):
        self.db("Snooze pressed")

        undone_time = None

        if self.lid.raised:
            undone_time = self.undo(quiet=True)

        if self.now() - self.last_raised_time < self.alarm_threshold_ms:
            if undone_time:
                self.record_time(undone_time)
            return

        self.record_time(raised_time=self.now() - (self.alarm_threshold_ms - self.one_hour_ms))
        try:
            cp.play_file(self.SNOOZE_WAV)
        except:
            pass

    def buttonx(self, button):
        return getattr(cp, "button_{}".format(button))

    def update_lights(self):
        # lid.raised is a property that will always be true if the lid is raised.
        if self.lid.raised:
            cp.stop_tone()
            cp.pixels.fill(0)
        else:
            delta = self.now() - self.last_raised_time
            if delta > self.alarm_threshold_ms:
                self.alarm()
            elif delta > self.red_threshold_ms:
                cp.pixels.fill(self.colors["red"])
            elif delta > self.yellow_threshold_ms:
                cp.pixels.fill(self.colors["yellow"])
            else:
                cp.pixels.fill(self.colors["green"])

    def handle_buttons(self):
        presses = set(filter(self.buttonx, ["a", "b"]))
        new_presses = presses - self.prev_presses
        self.prev_presses = presses
        for button in new_presses:
            if button == "a":
                self.undo()
            elif button == "b":
                self.snooze()

    def __call__(self):
        # calling the Lid object returns true only once per lid raising.
        if self.lid():
            self.record_time()
            self.alarm(alarm_state=False)

        self.update_lights()
        self.handle_buttons()

timer = Timer()
while True:
    timer()
