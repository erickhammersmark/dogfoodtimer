# dogfoodtimer
This is CircuitPython code for a dog food timer on an Adafruit Circuit Playground Express or Bluefruit. You can find more information about this project at https://ninetypercentfinished.com/2021/05/17/dog-food-timer/.

My giant docstrings made the program too big to load on a CPX, so I will preserve them here.

```
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
```
