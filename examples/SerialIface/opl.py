import struct

import serial

class ArduinoOpl:

  STARTUP_MSG = b'HLO!\n'
  READY_CMD = b'BUF?\n'
  ACK_RSP = b'k'
  BINARY_CMD_SIZE = 5
  RESET_CMD = b'\x00' * BINARY_CMD_SIZE


  def __init__(self, portname, baudrate=115200, debug=False):
    self.port = serial.Serial(portname, baudrate, timeout=None)
    self.ready = False
    self.n_outstanding = 0
    self.debug = debug

    # Opening port resets Arduino. Wait for ready message.
    self.wait_for_rsp(self.STARTUP_MSG)

    self._debug('Tx: %s' % self.READY_CMD)
    self.port.write(self.READY_CMD)
    opl_rx_buf_bytes = int(self.port.readline())
    self._debug('Rx buffer size: %d bytes' % opl_rx_buf_bytes)
    self.max_write_ahead = opl_rx_buf_bytes // self.BINARY_CMD_SIZE
    self._status(self.READY_CMD)

    self.ready = True

  def wait_for_rsp(self, rsp):
    self._debug('Awaiting: %s' % rsp)
    rx = self.port.readline()
    self._debug('Rx: %s' % rx)
    if not rx.endswith(rsp):
      raise RuntimeError('Expected: %s, received: %s' % (rsp, rx))

  def wait_for_ack(self):
    rsp = self.port.read()
    if rsp != self.ACK_RSP:
      raise RuntimeError('Expected: %s, received: %s' % (rsp, self.ACK_RSP))
    self.n_outstanding -= 1

  def write_reg(self, addr, data, delay_us=0, predelay=False):
    if self.n_outstanding >= self.max_write_ahead:
      self.wait_for_ack()
    self.write_reg_unbuffered(addr, data, delay_us, predelay)

  def write_reg_unbuffered(self, addr, data, delay_us, predelay):
    delay_ms = delay_us // 1000
    delay_remainder = delay_us % 1000
    if predelay:
      delay_ms = -delay_ms

    cmd = struct.pack('!BBhB', addr, data, delay_ms, delay_remainder // 4)
    self.n_outstanding += 1
    self.port.write(cmd)
    self._debug('Tx: %s' % ['%02x' % b for b in cmd])
    if delay_us > 0:
      self._debug('%8d.%03d milliseconds' % (delay_ms, delay_remainder))
    self._status(cmd)

  def _status(self, last_tx):
    status = 'Initialized' if self.ready else 'Initializing'
    tx_txt = 'Tx: %s' % ' '.join('%02x' % b for b in last_tx)
    status_str = "STATUS %-12s BUFFERED: %5d   %s" % (status, self.n_outstanding, tx_txt)
    print("%s\r" % status_str.ljust(79), end='')

  def _debug(self, txt):
    if self.debug:
      print(txt)

  def close(self):
    while self.n_outstanding:
      self.wait_for_ack()
    self.port.write(self.RESET_CMD)
    self._status(self.RESET_CMD)
    self.port.close()
