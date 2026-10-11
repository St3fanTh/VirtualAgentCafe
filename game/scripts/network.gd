extends Node

signal frame_received(frame: Dictionary)
signal connection_changed(online: bool)

var peer := WebSocketPeer.new()
var url := "ws://127.0.0.1:8000/ws/events"
var online := false
var reconnect_at := 0.0
var backoff := 0.5
var enabled := true

func _ready() -> void:
	var backend := OS.get_environment("VAC_BACKEND_URL")
	if backend != "":
		url = backend.replace("http://", "ws://").replace("https://", "wss://") + "/ws/events"
	connect_now()

func connect_now() -> void:
	peer = WebSocketPeer.new()
	peer.inbound_buffer_size = 65536
	peer.max_queued_packets = 128
	var result := peer.connect_to_url(url)
	if result != OK:
		schedule_reconnect()

func _process(_delta: float) -> void:
	if not enabled:
		return
	peer.poll()
	var state := peer.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		if not online:
			online = true
			backoff = 0.5
			connection_changed.emit(true)
		for _index in range(mini(peer.get_available_packet_count(), 32)):
			var packet := peer.get_packet()
			if packet.size() > 65536:
				force_reconnect()
				return
			var value = JSON.parse_string(packet.get_string_from_utf8())
			if value is Dictionary:
				frame_received.emit(value)
	elif state == WebSocketPeer.STATE_CLOSED:
		if online:
			online = false
			connection_changed.emit(false)
			schedule_reconnect()
		if Time.get_ticks_msec() / 1000.0 >= reconnect_at:
			schedule_reconnect()
			connect_now()

func schedule_reconnect() -> void:
	reconnect_at = Time.get_ticks_msec() / 1000.0 + backoff
	backoff = minf(backoff * 2.0, 15.0)

func force_reconnect() -> void:
	peer.close()
	if online:
		online = false
		connection_changed.emit(false)
	schedule_reconnect()

func _exit_tree() -> void:
	peer.close()
