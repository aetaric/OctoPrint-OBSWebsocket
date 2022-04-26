# coding=utf-8
from __future__ import absolute_import, unicode_literals

import octoprint.plugin, octoprint.util

from obswebsocket import obsws, requests, events

import logging, time

class ObswebsocketPlugin(
    octoprint.plugin.StartupPlugin, 
    octoprint.plugin.EventHandlerPlugin, 
    octoprint.plugin.ShutdownPlugin, 
    octoprint.plugin.ProgressPlugin, 
    octoprint.plugin.SettingsPlugin, 
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.RestartNeedingPlugin):

    def __init__(self):
        self._logger = logging.getLogger(__name__)

        self.websocket = None
        self.streaming = False
        self.progress  = 0
        self.temps = None
        self.tempthread = None

    def on_startup(self, host, port):
        self._logger.info("OBS Websocket Plugin Connecting to OBS")
        self.websocket = obsws(
            self._settings.get(["host"]), 
            self._settings.get(["port"]), 
            self._settings.get(["password"]))
        self.websocket.register(self.on_streamup, events.StreamStarted)
        self.websocket.register(self.on_streamdown, events.StreamStopped)
        self._logger.info("Registered OBS events")
        self.websocket.connect()
        self._logger.info("Connected to OBS Version: %s" % 
            self.websocket.call(requests.GetVersion()).getObsStudioVersion())
        self._logger.info("OBS Websocket Plugin Started")

    def on_streamup(self, event):
        self.streaming = True
        self._logger.info("Stream Started")
    
    def on_streamdown(self, event):
        self.streaming = False
        self._logger.info("Stream Stopped")

    def on_after_startup(self):
        self.tempthread = octoprint.util.RepeatedTimer(2.0, self.update_temps)
        time.sleep(1)
        self.tempthread.start()
    
    def on_shutdown(self):
        self._logger.info("OBS Websocket Plugin Stopping")
        self.websocket.call(requests.StopStreaming())
        self.websocket.disconnect()
        self._logger.info("Disconnected from OBS")
        self.progress = 0
        self.websocket = None
        self.streaming = False
    
    def on_print_progress(self, storage, path, progress):
        self.progress = progress
        self.temps = self._printer.get_current_temperatures()
        if not self._settings.get(["progress"]) == "":
            if self._settings.get(["os"]) == "windows":
                self.websocket.call(requests.SetTextGDIPlusProperties(
                        source="progress", text="Progress: %d%%" % self.progress))
            elif self._settings.get(["os"]) == "mac" or self._settings.get(["os"]) == "linux":
                self.websocket.call(requests.SetTextFreetype2Properties(
                        source="progress", text="Progress: %d%%" % self.progress))
            self._logger.debug("Updated progress")
    
    def on_event(self, event, payload):
        if event == "PrintStarted":
            if not self.streaming:
                self.websocket.call(requests.StartStreaming())
        elif event in ["PrintDone","PrintCanceled"]:
            if self.streaming:
                self.websocket.call(requests.StopStreaming())

    def update_temps(self):
        if self.websocket.ws.connected:
            self.temps = self._printer.get_current_temperatures()
            if self._settings.get(["os"]) == "windows":
                if not self._settings.get(["tool-temp"]) == "":
                    self.websocket.call(requests.SetTextGDIPlusProperties(source="tool-temp", 
                        text="Tool: %.1f°C/%.1f°C" % 
                        (self.temps["tool0"]["actual"], self.temps["tool0"]["target"])))
                if not self._settings.get(["bed-temp"]) == "":
                    self.websocket.call(requests.SetTextGDIPlusProperties(source="bed-temp", 
                        text="Bed: %.1f°C/%.1f°C" % 
                        (self.temps["bed"]["actual"], self.temps["bed"]["target"])))
                self._logger.debug("Updated temps")
            elif self._settings.get(["os"]) == "mac" or self._settings.get(["os"]) == "linux":
                if not self._settings.get(["tool-temp"]) == "":
                    self.websocket.call(requests.SetTextFreetype2Properties(source="tool-temp", 
                        text="Tool: %.1f°C/%.1f°C" % 
                        (self.temps["tool0"]["actual"], self.temps["tool0"]["target"])))
                if not self._settings.get(["bed-temp"]) == "":
                    self.websocket.call(requests.SetTextFreetype2Properties(source="bed-temp", 
                        text="Bed: %.1f°C/%.1f°C" % 
                        (self.temps["bed"]["actual"], self.temps["bed"]["target"])))
                self._logger.debug("Updated temps")
        else:
            self.websocket.connect()

    def get_settings_defaults(self):
        return dict(
            port = 4444,
            password = "password",
            host = "127.0.0.1",
            os = "windows",
            progress = "progress",
            tool = "tool-temp",
            bed = "bed-temp"
        )
    
    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._logger.info("Settings Saved")

        self.websocket.disconnect()
        self.websocket = obsws(
            self._settings.get(["host"]), 
            self._settings.get(["port"]), 
            self._settings.get(["password"]))
        self.websocket.register(self.on_streamup, events.StreamStarted)
        self.websocket.register(self.on_streamdown, events.StreamStopped)
        self.websocket.connect()

        self.tempthread = octoprint.util.RepeatedTimer(2.0, self.update_temps)
        time.sleep(1)
        self.tempthread.start()

        self._logger.info("Reconnected to OBS")
    
    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "obswebsocket": {
                "displayName": "Obswebsocket Plugin",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "aetaric",
                "repo": "OctoPrint-OBSWebsocket",
                "current": self._plugin_version,

                # update method: pip
                "pip": "https://github.com/aetaric/OctoPrint-OBSWebsocket/archive/{target_version}.zip",
            }
        }

__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = ObswebsocketPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
