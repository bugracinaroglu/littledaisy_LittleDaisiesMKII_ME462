def clamp(value, low, high):
    return max(low, min(value, high))


class LowPassFilter:
    def __init__(self, alpha=0.75, initial_value=0.0):
        self.alpha = alpha
        self.value = initial_value

    def reset(self, value=0.0):
        self.value = value

    def update(self, new_value):
        self.value = (
            self.alpha * self.value +
            (1.0 - self.alpha) * new_value
        )

        return self.value


class RateLimiter:
    def __init__(self, max_step=2.0, initial_value=90.0):
        self.max_step = max_step
        self.value = initial_value

    def reset(self, value):
        self.value = value

    def update(self, target_value):
        delta = target_value - self.value
        delta = clamp(delta, -self.max_step, self.max_step)

        self.value += delta
        return self.value