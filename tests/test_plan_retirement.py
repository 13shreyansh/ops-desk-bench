"""Small operational regressions for invalidated plans and dependent seat commitments."""
import unittest
from opsdesk.env import OpsDesk, PaxState
from opsdesk.world import Flight, Booking, Event
from opsdesk.verify import stale_plan_records


def desk(kind):
    e = OpsDesk(1)
    def flight(fid, origin, dest, dep, arr):
        return Flight(fid, origin, dest, dep, arr, dep, arr, 'E190', 100, fid)
    e.flights = {
        'OLD': flight('OLD', 'ARN', 'CPH', 900, 1000),
        'FEED': flight('FEED', 'ARN', 'HEL', 480, 540),
        'CONNECT': flight('CONNECT', 'HEL', 'CPH', 600, 660),
        'DIRECT': flight('DIRECT', 'ARN', 'CPH', 550, 650),
    }
    e.bookings = {'TEST01': Booking('TEST01', 20, 'medical', 'ARN', 'CPH', ['OLD'], 1000, booked_seq=1),
                  'FILLER': Booking('FILLER', 20, 'standard', 'HEL', 'CPH', ['CONNECT'], 660, booked_seq=0)}
    e.state = {'TEST01': PaxState('ARN', 0), 'FILLER': PaxState('HEL', 0)}
    e.original = {p:list(b.itinerary) for p,b in e.bookings.items()}
    e.log, e.events, e.fired, e.dyn_alerts = [], [], [], []
    e.problem_ticks = {}
    e._dirty, e.seq = True, 1
    result = e.tool('rebook', {'changes':[{'pnr':'TEST01', 'flights':['FEED','CONNECT']}]})
    assert result['results'][0]['ok']
    payload = {'flights':['FEED']} if kind == 'cancel' else ({'flight':'FEED', 'minutes':150} if kind == 'delay' else {'flight':'CONNECT','aircraft':'SF340'})
    e.events = [Event('CHANGE', 420, kind, 'The published operational constraints changed.', payload)]
    e.tool('advance_clock', {'minutes':60})
    return e


class PlanRetirementTests(unittest.TestCase):
    def test_cancellation_keeps_dependent_seats_until_repair(self):
        e = desk('cancel')
        rows = stale_plan_records(e)
        self.assertEqual(rows[0]['dependent_flights'], ['CONNECT'])
        self.assertFalse(rows[0]['retired'])
        self.assertEqual(e.booked('CONNECT'), 40)
        result = e.tool('rebook', {'changes':[{'pnr':'TEST01','flights':['DIRECT']}]})
        self.assertTrue(result['results'][0]['ok'])
        self.assertTrue(stale_plan_records(e)[0]['retired'])
        self.assertEqual(e.booked('CONNECT'), 20)
        self.assertEqual(e.booked('FEED'), 0)

    def test_changed_constraints_invalidate_accepted_plans(self):
        for kind in ['delay','downgauge']:
            with self.subTest(kind=kind):
                e = desk(kind)
                rows = stale_plan_records(e)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['cause'], kind)
                self.assertFalse(rows[0]['retired'])
                self.assertTrue(e.problems('TEST01'))

    def test_dynamic_knock_on_invalidates_dependent_connection(self):
        e = desk('cancel')
        e.events, e.fired, e.log = [], [], [l for l in e.log if l.kind == 'rebook']
        e.flights['FEED'].status = 'scheduled'
        e.flights['UP'] = Flight('UP', 'CPH', 'ARN', 400, 460, 430, 490, 'E190', 100, e.flights['FEED'].tail)
        e._fly_until(440)
        self.assertEqual(e.flights['FEED'].eta, 590)
        self.assertTrue(e.problems('TEST01'))
        self.assertEqual(e.booked('CONNECT'), 40)
        rows = stale_plan_records(e)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['cause'], 'knock_on')
        self.assertEqual(rows[0]['dependent_flights'], ['CONNECT'])
        self.assertFalse(rows[0]['retired'])
        e.tool('rebook', {'changes':[{'pnr':'TEST01','flights':['DIRECT']}]})
        self.assertTrue(stale_plan_records(e)[0]['retired'])
        self.assertEqual(e.booked('CONNECT'), 20)

    def test_onward_constraint_changes_while_airborne_are_recorded(self):
        for kind in ['cancel', 'downgauge']:
            with self.subTest(kind=kind):
                e = desk('cancel')
                e.flights['FEED'].status = 'scheduled'
                e.log = [l for l in e.log if l.kind == 'rebook']
                e.fired = []
                payload = {'flights':['CONNECT']} if kind == 'cancel' else {'flight':'CONNECT','aircraft':'SF340'}
                e.events = [Event('AIRBORNE-CHANGE',480,kind,'Onward constraint changed.',payload)]
                e.tool('advance_clock', {'minutes':60})
                self.assertIsNone(e.state['TEST01'].location)
                rows = stale_plan_records(e)
                self.assertEqual(len(rows),1)
                self.assertFalse(rows[0]['retired'])
                self.assertEqual(e.booked('CONNECT'),40)
                e.tool('advance_clock', {'minutes':60})
                self.assertEqual(e.state['TEST01'].location,'HEL')
                e.flights['HELNEW'] = Flight('HELNEW','HEL','CPH',610,670,610,670,'E190',100,'NEW')
                response = e.tool('rebook', {'changes':[{'pnr':'TEST01','flights':['HELNEW']}]})
                self.assertTrue(response['results'][0]['ok'])
                self.assertTrue(stale_plan_records(e)[0]['retired'])
                self.assertEqual(e.booked('CONNECT'),20)

    def test_failed_repair_cannot_retire_the_plan(self):
        e = desk('cancel')
        result = e.tool('rebook', {'changes':[{'pnr':'TEST01','flights':['FEED','CONNECT']}]})
        self.assertFalse(result['results'][0]['ok'])
        self.assertFalse(stale_plan_records(e)[0]['retired'])
        self.assertEqual(e.booked('CONNECT'), 40)

if __name__ == '__main__':
    unittest.main()
