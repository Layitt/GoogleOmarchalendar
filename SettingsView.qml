import QtQuick
import qs.Commons
import qs.Ui

// The calendar's settings page, shown in place of the month grid.
//
// Kept in its own file rather than folded into Panel.qml: the panel is
// already long, and everything here is presentation over values the panel
// owns. This component reads state and emits intent, it never writes
// shell.json itself.
Column {
  id: root

  property color foreground: "white"
  property string fontFamily: ""

  property string language: "es"
  property string weatherLocation: ""

  property var calendars: []
  property var hiddenCalendars: []
  property bool showYearProgress: false
  property bool weekStartsMonday: true
  property bool showWorkingLocation: false
  property bool hideDeclined: false
  property int announceLeadMinutes: 15

  property string syncedAt: ""
  property string sourceLabel: ""
  property int eventCount: 0
  property string syncState: "missing"
  property string setupCommand: ""
  property bool setupCommandCopied: false

  signal languagePicked(string lang)
  signal weatherLocationPicked(string location)
  signal calendarToggled(string calendarId)
  signal yearProgressToggled()
  signal weekStartToggled()
  signal workingLocationToggled()
  signal hideDeclinedToggled()
  signal leadMinutesPicked(int minutes)
  signal setupCommandCopyRequested()

  readonly property color muted: Qt.darker(foreground, 1.5)
  readonly property color faint: Qt.darker(foreground, 1.9)

  spacing: Style.space(10)

  component SectionTitle: Text {
    color: root.faint
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    font.letterSpacing: 1
    font.bold: true
  }

  // A row that reads as a switch without pulling in a control library the
  // rest of this plugin does not use.
  component ToggleRow: Rectangle {
    id: toggle

    property string label: ""
    property string hint: ""
    property bool checked: false
    property color swatch: "transparent"

    signal activated()

    width: parent ? parent.width : 0
    height: toggleBody.height + Style.space(6)
    radius: Style.cornerRadius
    color: hovered.hovered
      ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.06)
      : "transparent"

    HoverHandler { id: hovered }
    TapHandler { onTapped: toggle.activated() }

    Row {
      id: toggleBody
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.leftMargin: Style.space(3)
      anchors.rightMargin: Style.space(3)
      anchors.verticalCenter: parent.verticalCenter
      spacing: Style.space(4)

      Text {
        anchors.verticalCenter: parent.verticalCenter
        width: Style.space(14)
        text: toggle.checked ? "✓" : ""
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
      }

      Rectangle {
        anchors.verticalCenter: parent.verticalCenter
        visible: toggle.swatch != "transparent"
        width: Style.space(4)
        height: width
        radius: width / 2
        color: toggle.checked ? toggle.swatch : "transparent"
        border.width: Style.spacing.hairline
        border.color: toggle.swatch
      }

      Column {
        anchors.verticalCenter: parent.verticalCenter
        width: toggleBody.width - Style.space(26)
        spacing: Style.space(1)

        Text {
          width: parent.width
          text: toggle.label
          color: toggle.checked ? root.foreground : root.muted
          font.family: root.fontFamily
          font.pixelSize: Style.font.bodySmall
          elide: Text.ElideRight
        }

        Text {
          width: parent.width
          visible: toggle.hint !== ""
          text: toggle.hint
          color: root.faint
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
          elide: Text.ElideRight
        }
      }
    }
  }

  // ---- Language / Idioma ----

  SectionTitle { text: root.language === "en" ? "LANGUAGE" : "IDIOMA" }

  Row {
    spacing: Style.space(6)

    Rectangle {
      readonly property bool active: root.language === "es"
      width: esLabel.implicitWidth + Style.space(20)
      height: Style.space(26)
      radius: height / 2
      color: active
        ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.14)
        : "transparent"
      border.width: Style.spacing.hairline
      border.color: active ? root.muted : Qt.darker(root.foreground, 2.4)

      Text {
        id: esLabel
        anchors.centerIn: parent
        text: "Español"
        color: parent.active ? root.foreground : root.faint
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: parent.active
      }

      TapHandler { onTapped: root.languagePicked("es") }
    }

    Rectangle {
      readonly property bool active: root.language === "en"
      width: enLabel.implicitWidth + Style.space(20)
      height: Style.space(26)
      radius: height / 2
      color: active
        ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.14)
        : "transparent"
      border.width: Style.spacing.hairline
      border.color: active ? root.muted : Qt.darker(root.foreground, 2.4)

      Text {
        id: enLabel
        anchors.centerIn: parent
        text: "English"
        color: parent.active ? root.foreground : root.faint
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: parent.active
      }

      TapHandler { onTapped: root.languagePicked("en") }
    }
  }

  // ---- Weather Location / Ubicación del Clima ----

  SectionTitle { text: root.language === "en" ? "WEATHER LOCATION" : "UBICACIÓN DEL CLIMA" }

  Text {
    width: parent.width
    text: root.language === "en"
      ? "Enter city name (e.g. Morelia, Madrid, Tokyo) or 'Auto':"
      : "Escribe una ciudad (ej. Morelia, Madrid, Tokio) o 'Auto':"
    color: root.faint
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }

  TextField {
    id: weatherInput
    width: parent.width
    text: root.weatherLocation || ""
    placeholderText: "Auto (IP detection)"
    foreground: root.foreground
    font.family: root.fontFamily
    onAccepted: root.weatherLocationPicked(text)
    onEditingFinished: root.weatherLocationPicked(text)
  }

  // ---- Calendars ----

  SectionTitle { text: root.language === "en" ? "CALENDARS" : "CALENDARIOS" }

  Text {
    width: parent.width
    visible: root.calendars.length === 0
    text: root.language === "en" ? "No calendars synced." : "No hay calendarios sincronizados."
    color: root.faint
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }

  Repeater {
    model: root.calendars

    ToggleRow {
      required property var modelData

      label: modelData.name
      swatch: modelData.color
      checked: root.hiddenCalendars.indexOf(modelData.id) === -1
      onActivated: root.calendarToggled(modelData.id)
    }
  }

  // ---- Display ----

  SectionTitle { text: root.language === "en" ? "DISPLAY" : "VISUALIZACIÓN" }

  ToggleRow {
    label: root.language === "en" ? "Start weeks on Monday" : "Iniciar semanas en lunes"
    hint: root.language === "en" ? "Disabled starts the week on Sunday" : "Desactivado inicia la semana en domingo"
    checked: root.weekStartsMonday
    onActivated: root.weekStartToggled()
  }

  ToggleRow {
    label: root.language === "en" ? "Working-location events" : "Eventos de ubicación de trabajo"
    hint: root.language === "en" ? "Google's remote markers, hidden by default" : "Marcadores de trabajo remoto de Google, ocultos por defecto"
    checked: root.showWorkingLocation
    onActivated: root.workingLocationToggled()
  }

  ToggleRow {
    label: root.language === "en" ? "Declined invitations" : "Invitaciones rechazadas"
    hint: root.language === "en" ? "Struck through when enabled" : "Se muestran tachadas al estar activado"
    checked: !root.hideDeclined
    onActivated: root.hideDeclinedToggled()
  }

  ToggleRow {
    label: root.language === "en" ? "Year and life progress" : "Progreso de año y vida"
    hint: root.language === "en" ? "Time-meter bars, disabled by default" : "Barras de progreso de tiempo, desactivadas por defecto"
    checked: root.showYearProgress
    onActivated: root.yearProgressToggled()
  }

  // ---- Bar ----

  SectionTitle { text: root.language === "en" ? "BAR LABEL" : "ETIQUETA DE LA BARRA" }

  Text {
    width: parent.width
    text: root.language === "en"
      ? "How far ahead the bar announces the next event."
      : "Con cuánta antelación la barra anuncia el siguiente evento."
    color: root.faint
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap
  }

  Row {
    spacing: Style.space(3)

    Repeater {
      model: [0, 5, 15, 30, 60]

      Rectangle {
        required property var modelData

        readonly property bool active: modelData === root.announceLeadMinutes

        width: leadLabel.width + Style.space(8)
        height: leadLabel.height + Style.space(4)
        radius: height / 2
        color: active
          ? Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.14)
          : "transparent"
        border.width: Style.spacing.hairline
        border.color: active ? root.muted : Qt.darker(root.foreground, 2.4)

        Text {
          id: leadLabel
          anchors.centerIn: parent
          text: modelData === 0 ? (root.language === "en" ? "Never" : "Nunca") : (modelData + " min")
          color: active ? root.foreground : root.faint
          font.family: root.fontFamily
          font.pixelSize: Style.font.caption
        }

        TapHandler { onTapped: root.leadMinutesPicked(modelData) }
      }
    }
  }

  // ---- Sync status ----

  SectionTitle { text: root.language === "en" ? "SYNC" : "SINCRONIZACIÓN" }

  Text {
    width: parent.width
    color: root.syncState === "missing" && syncHover.hovered ? root.foreground : root.faint
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    wrapMode: Text.WordWrap

    HoverHandler {
      id: syncHover
      enabled: root.syncState === "missing"
      cursorShape: Qt.PointingHandCursor
    }

    TapHandler {
      enabled: root.syncState === "missing"
      onTapped: root.setupCommandCopyRequested()
    }

    text: {
      if (root.syncState === "missing") {
        if (root.language === "en") {
          return root.setupCommandCopied
            ? "Copied. Paste it in a terminal:\n" + root.setupCommand
            : "No calendar connected. Click to copy then run:\n" + root.setupCommand
        }
        return root.setupCommandCopied
          ? "Copiado. Pégalo en una terminal:\n" + root.setupCommand
          : "No hay calendario conectado. Clic para copiar y luego ejecutar:\n" + root.setupCommand
      }
      if (root.syncState === "version") {
        return root.language === "en"
          ? "The events file was written by a newer version."
          : "El archivo de eventos fue escrito por una versión más reciente."
      }

      var line = root.language === "en"
        ? (root.eventCount + " events from " + root.sourceLabel)
        : (root.eventCount + " eventos de " + root.sourceLabel)
      if (root.syncState === "stale") {
        return root.language === "en"
          ? (line + "\nLast sync looks old. Check: journalctl --user -u omarchy-calendar-sync")
          : (line + "\nLa última sincronización parece antigua. Revisa: journalctl --user -u omarchy-calendar-sync")
      }
      return root.language === "en"
        ? (line + "\nLast synced " + root.syncedAt)
        : (line + "\nÚltima sincronización " + root.syncedAt)
    }
  }
}
