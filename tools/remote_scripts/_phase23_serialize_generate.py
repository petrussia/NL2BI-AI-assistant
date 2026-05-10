"""Phase 23 — install a global GPU lock so concurrent BG threads serialize
their model.generate calls. Critical: BQ FULL is already running. We
monkey-patch _MDL_PLAN.generate and _MDL_EMIT.generate to acquire the
lock before forward, so even the existing BQ FULL thread will pick up
the lock once it next enters generate().
"""
import threading

g = globals()
if g.get('_PHASE23_GEN_LOCK') is None:
    g['_PHASE23_GEN_LOCK'] = threading.Lock()
    print('CREATED_LOCK')
else:
    print('LOCK_ALREADY_EXISTS')

LOCK = g['_PHASE23_GEN_LOCK']


def _wrap(model, label):
    if getattr(model, '_phase23_wrapped', False):
        print(f'{label} ALREADY_WRAPPED')
        return
    orig = model.generate.__func__ if hasattr(model.generate, '__func__') else model.generate

    def serialized_generate(*args, **kwargs):
        with LOCK:
            return orig(model, *args, **kwargs) if hasattr(model.generate, '__func__') else orig(*args, **kwargs)

    # Replace at instance level
    import types
    model.generate = types.MethodType(lambda self, *a, **k:
                                            (lambda: orig(self, *a, **k) if hasattr(type(self).generate, '__func__') else orig(*a, **k))()
                                            if False else (
                                                (lambda: (LOCK.acquire(), (orig(self, *a, **k) if hasattr(type(self).generate, '__func__') else orig(*a, **k)) if False else None)[1])()
                                            ),
                                          model)
    # simpler: just attach a wrapper method
    def _gen(self, *a, **k):
        with LOCK:
            return orig.__func__(self, *a, **k) if hasattr(orig, '__func__') else orig(*a, **k)

    # The above is messy. Use a clean approach:
    underlying = type(model).generate
    def _generate_serialized(self, *a, **k):
        with LOCK:
            return underlying(self, *a, **k)
    model.generate = _generate_serialized.__get__(model, type(model))
    model._phase23_wrapped = True
    print(f'{label} WRAPPED')


for slot, label in [('_MDL_PLAN', 'planner_30b'), ('_MDL_EMIT', 'emitter_7b')]:
    m = g.get(slot)
    if m is None:
        print(f'{slot} NOT_LOADED')
    else:
        _wrap(m, label)


print('PHASE23_SERIALIZE_DONE')
