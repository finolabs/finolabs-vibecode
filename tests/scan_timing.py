"""Bound scanner regressions even while the regex engine holds the GIL."""
import multiprocessing
import time


def timed_scan(case, operation):
    context = multiprocessing.get_context('fork')
    reader, writer = context.Pipe(duplex=False)

    def run():
        reader.close()
        try:
            writer.send(('ok', operation()))
        except Exception:
            writer.send(('error', None))
        finally:
            writer.close()

    worker = context.Process(target=run)
    started = time.monotonic()
    worker.start()
    writer.close()
    try:
        case.assertTrue(reader.poll(5), 'scanner exceeded five-second budget; content suppressed')
        status, result = reader.recv()
        case.assertEqual(status, 'ok', 'scanner failed; content suppressed')
        case.assertLess(time.monotonic() - started, 5, 'scanner exceeded budget')
        return result
    finally:
        if worker.is_alive():
            worker.terminate()
        worker.join(1)
        if worker.is_alive():
            worker.kill()
            worker.join()
        reader.close()
