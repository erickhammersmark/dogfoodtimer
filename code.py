import time
from adafruit_circuitplayground import cp


class DogfoodTimerCommon(object):
    colors = [ (0, 255, 0), (255, 255, 0), (255, 0, 0) ]
    def now(self):
        return int(time.monotonic() * 1000)


class Lid(DogfoodTimerCommon):
    '''
    Debounces accelerometer state for cpx.acceleration,
    specifically looking for a transition from high Z
    and low X + Y to low Z and high X + Y (i.e. when the
    board is flat, return False. When the board is on edge,
    return True.

    Depends on the instance being called directly to update
    its state. Calling the instance will return True one time
    per lid raise.

    lid = Lid()
    if lid.raised:
      print("this is impossible")
    if lid():
      print("because of debounce, this is also impossible")
    if lid():
      print("this could work now")
    if lid.raised:
      print("this too")
    if lid.lowered:
      print("this would always have worked, but only by truthy/falsey happenstance.")
      print("transition to the lowered state is also debounced.")
    '''

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
    '''
    Call an instance of this to update the alarm state of the cpx.
    Alarm state == pixels flashing red at 0.5Hz and beeping every minute.
    You have to keep calling it to keep getting the behaviors.

    The module behaves this way instead of, say, using cp.tone() to beep
    for beep_on_time_ms or time.sleep() to flash because none of those things
    can happen asynchronously. We do not want beeps and flashes to block the
    rest of the timer operations (such as detecting the lid raising or a
    button being pushed). In other python environments, this logic could be
    simpler and run in the background using "threading" or "multiprocessing".
    In CircuitPython, we do not have these.
    '''

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
                cp.pixels.fill(self.colors[2])
            else:
                cp.pixels.fill(0)



class Timer(DogfoodTimerCommon):
    '''
    Implements an accelerometer-based timer for an Adafruit Circuit Playground
    Express or Bluefruit.

    Example:

        timer = Timer()
        while True:
            timer()

    This module depends on the instance being called continuously to measure
    state and update its behaviors. It does no background work at all.

    When the cp (Circuit Playground Express or Bluefruit) remains in the flat
    orientation for at least 100ms, the lid is considered closed. When the cp
    is not flat (literally, when abs(Z) is < 4 and abs(X) + abx(Y) > 4) for
    at least 100ms, the lid is considered raised. The timer tracks a history
    of raised times for purposes of undo().

    Pressing button A on the cp will undo the last recorded raised time, and
    pressing it more than once will keep undoing times until there are no more
    times to undo. There is no redo.

    Pressing button B will snooze the timer by setting the raised time to its
    current value plus one hour.
    '''

    one_hour_ms          = 3600000
    green_threshold_ms   = 0
    yellow_threshold_ms  = one_hour_ms * 4
    red_threshold_ms     = one_hour_ms * 8
    alarm_threshold_ms   = one_hour_ms * 12

    #yellow_threshold_ms  = 2000 # 2 seconds
    #red_threshold_ms     = 4000 # 4 seconds
    #alarm_threshold_ms   = 6000 # 6 seconds

    UNDO_WAV = "undo.wav"
    SNOOZE_WAV = "snooze.wav"

    def __init__(self):
        self.post()
        self.lid = Lid()
        self.alarm = Alarm()
        self.history = []
        self.prev_presses = set()
        self.last_raised_time = self.now()

    def post(self):
        '''
        Simple power on self test
        briefly sets the LEDs to each of the colors.
        '''
        for color in self.colors:
            cp.pixels.fill(color)
            time.sleep(0.5)
        cp.pixels.fill(0)

    def undo(self, quiet=False):
        if self.history:
            self.last_raised_time = self.history.pop(-1)
            if not quiet:
                cp.play_file(self.UNDO_WAV)

    def record_time(self, raised_time=None):
        raised_time = raised_time or self.now()
        self.history.append(self.last_raised_time)
        self.history = self.history[-10:]
        self.last_raised_time = raised_time

    def snooze(self):
        '''
        Because this is intended to run on a board that is mounted under
        the lifting lid, the act of raising it to push the snooze button
        will itself reset the timer, defeating the point of snoozing.
        When the snooze button is pushed, first undo, then snooze.
        '''
        if self.now() - self.last_raised_time < alarm_threshold_ms:
            return

        if self.lid.raised:
            self.undo(quiet=True)

        self.record_time(raised_time=self.now() - (alarm_threshold_ms - one_hour_ms))
        cp.play_file(self.SNOOZE_WAV)

    def __call__(self):
        '''
        Call your instance of Timer as often as you want the behaviors
        updated (lights changing color, flashing and beeping timeing,
        detecting and debouncing lid raises, etc. This is basically the
        loop() function ported from an Arduino version of this project.
        '''

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
                cp.pixels.fill(self.colors[2])
            elif delta > self.yellow_threshold_ms:
                cp.pixels.fill(self.colors[1])
            else:
                cp.pixels.fill(self.colors[0])

        presses = cp.were_pressed
        new_presses = presses - self.prev_presses
        self.prev_presses = presses
        for button in new_presses:
            if button == "A":
                self.undo()
            elif button == "B":
                self.snooze()

timer = Timer()
while True:
    timer()
