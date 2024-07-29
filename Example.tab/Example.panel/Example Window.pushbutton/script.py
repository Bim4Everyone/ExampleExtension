# coding=utf-8

# from typing import Iterable
# from typing import Optional

import clr
import pyevent

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from Autodesk.Revit.DB import *
from Autodesk.Revit.ApplicationServices import Application

from System.Windows.Input import ICommand
from System.Collections.ObjectModel import ObservableCollection

from pyrevit import forms
from pyrevit import revit
from pyrevit import script
from pyrevit import HOST_APP
from pyrevit import EXEC_PARAMS
from pyrevit.userconfig import user_config
from pyrevit.forms import reactive, Reactive

from dosymep_libs.bim4everyone import *


section_name = EXEC_PARAMS.command_name + "." + HOST_APP.doc.Title.split("_")[0]

class CustomLocation:
    def __init__(self, start, finish):
        # type: (XYZ, XYZ) -> None
        self.start = start
        self.finish = finish

    def __str__(self):
        return "{} - {}".format(self.start, self.finish)


class PluginConfig:
    def __init__(self):
        if not(user_config.has_section(section_name)):
            section = user_config.add_section(section_name)
            section.set_option("height", 20)
        self.__height = float(user_config.get_section(section_name).get_option("height", 20))
        self.__wall_type_id = user_config.get_section(section_name).get_option("wall_type_id", ElementId.InvalidElementId.GetIdValue())


    @property
    def height(self):
        return self.__height

    @height.setter
    def height(self, value):
        self.__height = value

    @property
    def wall_type_id(self):
        return self.__wall_type_id

    @wall_type_id.setter
    def wall_type_id(self, value):
        self.__wall_type_id = value

    @staticmethod
    def save_config(config):
        # type: (PluginConfig) -> None
        section = user_config.get_section(section_name)
        section.set_option("height", config.height)
        section.set_option("wall_type_id", config.wall_type_id)
        user_config.save_changes()


class WallRepository:
    def __init__(self, document, application):
        # type: (Document, Application) -> None
        self.document = document
        self.application = application

    def get_walls(self):
        return (FilteredElementCollector(self.document, self.document.ActiveView.Id)
                .OfClass(Wall)
                .WhereElementIsNotElementType()
                .ToElements())

    def get_wall_types(self):
        return (FilteredElementCollector(self.document)
                .OfClass(WallType)
                .WhereElementIsElementType()
                .ToElements())

    def create_wall(self, location, wall_type, height):
        # type: (CustomLocation, WallType, float) -> Wall
        curve = Line.CreateBound(location.start, location.finish)
        return Wall.Create(self.document,
                           curve, wall_type.Id, self.__get_level().Id, height, 0, False, False)

    def __get_level(self):
        return self.document.ActiveView.GenLevel

    def active_view_is_plan(self):
        return isinstance(self.document.ActiveView, ViewPlan)


class ShowWallCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view, view_model, wall_repository):
        ICommand.__init__(self)
        self.__view = view
        self.__view_model = view_model
        self.__wall_repository = wall_repository

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):
        revit.get_selection().set_to([parameter.id])



class SelectLocationCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view, view_model, wall_repository):
        ICommand.__init__(self)
        self.__view = view
        self.__view_model = view_model
        self.__wall_repository = wall_repository

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):
        self.__view.Hide()
        try:
            start = None  # type: Optional[XYZ]
            finish = None  # type: Optional[XYZ]

            while start is None or finish is None:
                if not start:
                    with forms.WarningBar(title="Please select start point"):
                        start = revit.pick_point("Please select start point")

                if not finish:
                    with forms.WarningBar(title="Please select finish point"):
                        finish = revit.pick_point("Please select finish point")

            self.__view_model.custom_location = CustomLocation(start, finish)
        finally:
            self.__view.show_dialog()


class LoadWindowCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view, view_model, wall_repository, plugin_config):
        # type: (ExampleWindow, MainViewModel, WallRepository, PluginConfig) -> None

        ICommand.__init__(self)
        self.__view = view
        self.__view_model = view_model
        self.__wall_repository = wall_repository
        self.__plugin_config = plugin_config

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):
        self.__view_model.walls = MainViewModel.create_observable(self.__wall_repository.get_walls())
        self.__view_model.wall_types = MainViewModel.create_observable(self.__wall_repository.get_wall_types())

        self.__view_model.wall_type = next((wall for wall in self.__view_model.wall_types), None)
                                            #if wall.id.GetIdValue() == int(self.__view_model.plugin_config.wall_type_id)), None)
        self.__view_model.height = str(self.__plugin_config.height)


class AcceptWindowCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view, view_model, wall_repository):
        # type: (ExampleWindow, MainViewModel, WallRepository) -> None

        ICommand.__init__(self)
        self.__view = view
        self.__view_model = view_model # type: MainViewModel
        self.__wall_repository = wall_repository

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):
        self.__view_model.plugin_config.height = float(self.__view_model.height)
        self.__view_model.plugin_config.wall_type_id = self.__view_model.wall_type.id.GetIdValue()
        PluginConfig.save_config(self.__view_model.plugin_config)
        with revit.Transaction("Create wall"):
            wall = self.__wall_repository.create_wall(
                self.__view_model.custom_location, self.__view_model.wall_type.wall, float(self.__view_model.height))
            self.__view_model.walls.Add(WallViewModel(wall))


class WallViewModel(Reactive):
    def __init__(self, wall):
        # type: (Wall) -> None

        Reactive.__init__(self)
        self.wall = wall

    @property
    def id(self):
        return self.wall.Id

    @property
    def name(self):
        return Element.Name.__get__(self.wall)


class MainViewModel(Reactive):
    def __init__(self, view, wall_repository, plugin_config):
        # type: (ExampleWindow, WallRepository, PluginConfig) -> None

        Reactive.__init__(self)
        self.__view = view
        self.__wall_repository = wall_repository
        self.__plugin_config = plugin_config

        self.__load_command = LoadWindowCommand(view, self, self.__wall_repository, self.__plugin_config)
        self.__accept_command = AcceptWindowCommand(view, self, self.__wall_repository)
        self.__select_location_command = SelectLocationCommand(view, self, self.__wall_repository)
        self.__show_wall_command = ShowWallCommand(view, self, self.__wall_repository)

        self.__walls = None  # type: Optional[ObservableCollection[WallViewModel]]
        self.__wall_types = None  # type: Optional[ObservableCollection[WallViewModel]]

        self.__height = None # type: Optional[float]
        self.__wall_type = None  # type: Optional[WallViewModel]
        self.__custom_location = None  # type: Optional[CustomLocation]

        self.__error_text = None  # type: Optional[str]

    @property
    def load_command(self):
        return self.__load_command

    @property
    def accept_command(self):
        return self.__accept_command

    @property
    def plugin_config(self):
        return self.__plugin_config

    @property
    def select_location_command(self):
        return self.__select_location_command

    @property
    def show_wall_command(self):
        return self.__show_wall_command

    @reactive
    def walls(self):
        return self.__walls

    @walls.setter
    def walls(self, value):
        self.__walls = value

    @reactive
    def wall_types(self):
        return self.__wall_types

    @wall_types.setter
    def wall_types(self, value):
        self.__wall_types = value

    @reactive
    def height(self):
        return self.__height

    @height.setter
    def height(self, value):
        self.__height = value

    @reactive
    def wall_type(self):
        return self.__wall_type

    @wall_type.setter
    def wall_type(self, value):
        self.__wall_type = value

    @reactive
    def custom_location(self):
        return self.__custom_location

    @custom_location.setter
    def custom_location(self, value):
        self.__custom_location = value

    @reactive
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value

    @staticmethod
    def create_observable(enumerator):
        # type: (Iterable[Wall]) -> ObservableCollection[WallViewModel]
        return ObservableCollection[WallViewModel](WallViewModel(wall) for wall in enumerator)


class ExampleWindow(forms.WPFWindow):
    DialogResult = None  # type: bool

    def __init__(self):
        forms.WPFWindow.__init__(self, "ExampleWindow.xaml")

    def ButtonOk_Click(self, sender, e):
        self.DialogResult = True
        self.Close()

    def ButtonCancel_Click(self, sender, e):
        self.DialogResult = False
        self.Close()


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    window = ExampleWindow()
    wall_repo = WallRepository(HOST_APP.doc, HOST_APP.app)
    if(not(wall_repo.active_view_is_plan())):
        TaskDialog.Show(window.get_locale_string('TaskDialog.ActiveViewTitle'),
                        window.get_locale_string('TaskDialog.ActiveViewUserPromt'))
        script.exit()
    window.DataContext = MainViewModel(window, wall_repo, PluginConfig())


    if not window.ShowDialog():
        script.exit()


script_execute()
