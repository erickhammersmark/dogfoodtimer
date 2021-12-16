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
    beep_interval_ms = 60000 # time between sets of beeps (1 minute)
    beep_on_time_ms = 300    # the length of one beep (300ms)
    beep_off_time_ms = 1000  # the time between beeps in a set (1 second)
    n_beeps = 3              # the number of beeps in one set

    def __init__(self):
        self.state = False
        self.time = self.now()
        self.beep_time = 0

        _time = self.beep_interval_ms
        self.times = []
        for n in range(0, self.n_beeps):
            self.times.append((_time, True))
            _time += self.beep_on_time_ms
            self.times.append((_time, False))
            _time += self.beep_off_time_ms
        self.times.reverse()

    def beep(self):
        delta = self.now() - self.beep_time
        if delta < self.beep_interval_ms:
            return
        if delta > self.times[0][0]:
            cp.stop_tone()
            self.beep_time = self.now()
            return
        for _time in self.times:
            if delta > _time[0]:
                if _time[1] and not cp.switch:
                    cp.start_tone(1760)
                else:
                    cp.stop_tone()
                return

    def __call__(self):
        self.beep()
        if self.now() - self.time >= 1000:
            self.state = not self.state
            self.time = self.now()
            if self.state:
                cp.pixels.fill(self.colors["red"])
            else:
                cp.pixels.fill(0)


class Timer(DogfoodTimerCommon):
    one_hour_ms          = 3600000
    #one_hour_ms          =  500 # 500ms
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
        if self.history:
            self.last_raised_time = self.history.pop(-1)
            if not quiet:
                try:
                    cp.play_file(self.UNDO_WAV)
                except:
                    pass

    def record_time(self, raised_time=None):
        raised_time = raised_time or self.now()
        self.history.append(self.last_raised_time)
        self.history = self.history[-10:]
        self.last_raised_time = raised_time

    def snooze(self):
        self.db("Snooze pressed")

        if self.now() - self.last_raised_time < self.alarm_threshold_ms:
            return

        if self.lid.raised:
            self.undo(quiet=True)

        self.record_time(raised_time=self.now() - (self.alarm_threshold_ms - self.one_hour_ms))
        try:
            cp.play_file(self.SNOOZE_WAV)
        except:
            pass

    def buttonx(self, button):
        return getattr(cp, "button_{}".format(button))

    def __call__(self):
        # calling the object returns true only once per lid raising.
        if self.lid():
            self.record_time()

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

        presses = set(filter(self.buttonx, ["a", "b"]))
        new_presses = presses - self.prev_presses
        self.prev_presses = presses
        for button in new_presses:
            if button == "a":
                self.undo()
            elif button == "b":
                self.snooze()


timer = Timer()
while True:
    timer()
