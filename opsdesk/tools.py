"""Tool specs shared by the MCP server and the local agent runner (one source of truth)."""

TOOLS = [
    {"name": "get_status",
     "description": "Current sim time, shift end, number of alerts published and how many bookings currently have problems.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "read_alerts",
     "description": "All operations alerts published so far (cancellations, delays, notices, added flights), oldest first. "
                    "Pass `since` (an alert id) to get only newer ones.",
     "parameters": {"type": "object", "properties": {"since": {"type": "string"}}}},
    {"name": "list_flights",
     "description": "Published schedule with current times, status and free seats. Optional filters: origin, dest "
                    "(airport codes) and a departure window after/before as HH:MM (prefix '+1 ' for tomorrow). Max 60 rows (150 when origin or dest is given).",
     "parameters": {"type": "object", "properties": {
         "origin": {"type": "string"}, "dest": {"type": "string"},
         "after": {"type": "string"}, "before": {"type": "string"}}}},
    {"name": "get_flight",
     "description": "One flight with its manifest (bookings currently on it).",
     "parameters": {"type": "object", "properties": {"flight": {"type": "string"}}, "required": ["flight"]}},
    {"name": "get_booking",
     "description": "One booking: passengers, tier, deadline, current location, itinerary and any problems.",
     "parameters": {"type": "object", "properties": {"pnr": {"type": "string"}}, "required": ["pnr"]}},
    {"name": "find_disrupted_bookings",
     "description": "Every booking that will NOT reach its destination as currently booked (cancelled flight, "
                    "misconnection, missed flight, or will be denied boarding on an oversold flight). "
                    "Uses the current schedule only; it does not apply notices about future closures.",
     "parameters": {"type": "object", "properties": {}}},
    {"name": "search_itineraries",
     "description": "For up to 20 bookings, the legal itineraries (direct or via HEL) from where the group is now, "
                    "earliest arrival first, with free seats. Respects check-in cut-off and minimum connection time. "
                    "Does not apply notices about future closures.",
     "parameters": {"type": "object", "properties": {"pnrs": {"type": "array", "items": {"type": "string"}}},
                    "required": ["pnrs"]}},
    {"name": "rebook",
     "description": "Replace the remaining itinerary of up to 25 bookings. Each change is {pnr, flights:[...]}; "
                    "the whole group moves together. Changes are applied in order and each is validated "
                    "(seats, cut-off, connection time, route).",
     "parameters": {"type": "object", "properties": {"changes": {"type": "array", "items": {
         "type": "object", "properties": {"pnr": {"type": "string"},
                                          "flights": {"type": "array", "items": {"type": "string"}}},
         "required": ["pnr", "flights"]}}}, "required": ["changes"]}},
    {"name": "advance_clock",
     "description": "Let the operation run for 30 or 60 minutes. Flights depart and land, and new alerts may arrive. "
                    "Returns the new alerts.",
     "parameters": {"type": "object", "properties": {"minutes": {"type": "integer"}}}},
    {"name": "end_shift",
     "description": "End your shift and hand over. Nothing more can be changed afterwards; the rest of the "
                    "operation (including tomorrow's flights) runs without the desk.",
     "parameters": {"type": "object", "properties": {"handover": {"type": "string"}}}},
]
