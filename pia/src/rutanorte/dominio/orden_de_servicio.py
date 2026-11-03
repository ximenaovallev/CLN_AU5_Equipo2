"""Aggregate Root: OrdenDeServicio (estado, asignación, historial, incidencias, evidencias)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from .comunes import (
    ControlDeAltoValorPendiente,
    ErrorDeDominio,
    EventoDeDominio,
    OrdenNoGenerable,
    TransicionDeEstadoInvalida,
    ahora,
)
from .cotizacion import Cotizacion
from .eventos import (
    CargaDeAltoValorAutorizada,
    EntregaRegistrada,
    IncidenciaRegistrada,
    OrdenDeServicioGenerada,
    RecursosAsignados,
    ServicioCancelado,
)
from .valores import (
    Asignacion,
    Destinatario,
    Evidencia,
    Horario,
    Mercancia,
    PoliticaDeConservacion,
    Ubicacion,
)


class EstadoServicio(Enum):
    SOLICITADO = "SOLICITADO"
    COTIZADO = "COTIZADO"
    CONFIRMADO = "CONFIRMADO"
    UNIDAD_ASIGNADA = "UNIDAD_ASIGNADA"
    RECOLECTADO = "RECOLECTADO"
    EN_TRANSITO = "EN_TRANSITO"
    LLEGADA_A_DESTINO = "LLEGADA_A_DESTINO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"  # SUPUESTO S-04: terminación de un servicio aceptado (glosario: Cancelación)


class TipoDeIncidencia(Enum):
    UNIDAD_AVERIADA = "UNIDAD_AVERIADA"
    RETRASO = "RETRASO"
    MERCANCIA_DIFERENTE = "MERCANCIA_DIFERENTE"
    MERCANCIA_RECHAZADA = "MERCANCIA_RECHAZADA"
    DIRECCION_INCORRECTA = "DIRECCION_INCORRECTA"
    DESTINATARIO_AUSENTE = "DESTINATARIO_AUSENTE"
    ENTREGA_PARCIAL = "ENTREGA_PARCIAL"
    MERCANCIA_DANADA = "MERCANCIA_DANADA"


@dataclass(frozen=True)
class EntradaDeHistorial:
    fecha: datetime
    descripcion: str
    estado_resultante: EstadoServicio
    registrado_por: str


@dataclass(frozen=True)
class Cancelacion:
    """El glosario exige registrar quién solicita la cancelación y el motivo."""

    solicitado_por: str
    motivo: str
    fecha: datetime


@dataclass
class Incidencia:
    """Entity (identidad local dentro del agregado)."""

    id: int
    tipo: TipoDeIncidencia
    descripcion: str
    fecha_registro: datetime
    evidencias: list[Evidencia] = field(default_factory=list)


class OrdenDeServicio:
    def __init__(self, id: str, cotizacion_id: str, cliente_id: str, origen: Ubicacion,
                 destino: Ubicacion, mercancia: Mercancia, ruta: str, horario_recoleccion: Horario,
                 fecha_requerida: date | None = None):
        self.id = id
        self.cotizacion_id = cotizacion_id
        self.cliente_id = cliente_id
        self.origen = origen
        self.destino = destino
        self.mercancia = mercancia
        self.ruta = ruta
        self.horario_recoleccion = horario_recoleccion
        self.fecha_requerida = fecha_requerida
        self._alto_valor_autorizado = False
        self._cancelacion: Cancelacion | None = None
        self._fecha_entrega: datetime | None = None
        self._estado = EstadoServicio.CONFIRMADO
        self._asignacion: Asignacion | None = None
        self._historial: list[EntradaDeHistorial] = []
        self._incidencias: list[Incidencia] = []
        self._evidencias_recepcion: list[Evidencia] = []
        self._evidencias_entrega: list[Evidencia] = []
        self._destinatario: Destinatario | None = None
        self._eventos: list[EventoDeDominio] = []

    # ------------------------------ creación ------------------------------
    @classmethod
    def generar_desde(cls, id: str, cotizacion: Cotizacion, ruta: str,
                      horario_recoleccion: Horario, registrado_por: str = "Operaciones") -> OrdenDeServicio:
        if not cotizacion.esta_aceptada():
            raise OrdenNoGenerable(
                f"La orden solo se genera desde una cotización aceptada (cotización {cotizacion.id}: "
                f"{cotizacion.estado.value})."
            )
        s = cotizacion.solicitud
        orden = cls(id, cotizacion.id, cotizacion.cliente_id, s.origen, s.destino,
                    s.mercancia, ruta, horario_recoleccion, s.fecha_requerida)
        orden._registrar("Orden de servicio generada", registrado_por)
        orden._eventos.append(OrdenDeServicioGenerada(orden_id=id, cotizacion_id=cotizacion.id))
        return orden

    # ------------------------------ consultas del agregado ------------------------------
    def estado_actual(self) -> EstadoServicio:
        return self._estado

    @property
    def asignacion(self) -> Asignacion | None:
        return self._asignacion

    @property
    def historial(self) -> tuple[EntradaDeHistorial, ...]:
        return tuple(self._historial)

    @property
    def incidencias(self) -> tuple[Incidencia, ...]:
        return tuple(self._incidencias)

    @property
    def cancelacion(self) -> Cancelacion | None:
        return self._cancelacion

    @property
    def fecha_entrega(self) -> datetime | None:
        return self._fecha_entrega

    @property
    def alto_valor_autorizado(self) -> bool:
        return self._alto_valor_autorizado

    def evidencias(self, politica: PoliticaDeConservacion | None = None,
                   hoy: datetime | None = None) -> tuple[Evidencia, ...]:
        """Todas las evidencias asociadas a la orden; con política (S-03) solo las vigentes."""
        todas = [*self._evidencias_recepcion, *self._evidencias_entrega,
                 *(e for i in self._incidencias for e in i.evidencias)]
        if politica is None:
            return tuple(todas)
        momento = hoy or ahora()
        return tuple(e for e in todas if politica.conserva(e, momento))

    @property
    def destinatario(self) -> Destinatario | None:
        return self._destinatario

    @property
    def evidencias_entrega(self) -> tuple[Evidencia, ...]:
        return tuple(self._evidencias_entrega)

    def extraer_eventos(self) -> list[EventoDeDominio]:
        eventos, self._eventos = self._eventos, []
        return eventos

    # ------------------------------ comportamiento ------------------------------
    def asignar_recursos(self, asignacion: Asignacion, registrado_por: str = "Operaciones") -> None:
        """Asigna (o reasigna antes de la recolección) unidad y operador; conserva el historial."""
        self._exigir_estado("asignar recursos", EstadoServicio.CONFIRMADO, EstadoServicio.UNIDAD_ASIGNADA)
        if self.mercancia.alto_valor and not self._alto_valor_autorizado:
            raise ControlDeAltoValorPendiente(
                f"La orden {self.id} es de alto valor: Operaciones debe autorizarla antes de asignar recursos."
            )
        es_reasignacion = self._asignacion is not None
        if es_reasignacion:
            descripcion = (f"Asignación actualizada: unidad {self._asignacion.unidad_id}→{asignacion.unidad_id}, "
                           f"operador {self._asignacion.operador_id}→{asignacion.operador_id}")
        else:
            descripcion = f"Unidad {asignacion.unidad_id} y operador {asignacion.operador_id} asignados"
        self._asignacion = asignacion
        self._estado = EstadoServicio.UNIDAD_ASIGNADA
        self._registrar(descripcion, registrado_por)
        self._eventos.append(RecursosAsignados(orden_id=self.id, asignacion=asignacion,
                                               es_reasignacion=es_reasignacion))

    def autorizar_alto_valor(self, autorizado_por: str) -> None:
        """SUPUESTO S-02: la carga de alto valor se autoriza antes de asignar unidad y operador."""
        if not self.mercancia.alto_valor:
            raise ErrorDeDominio(f"La orden {self.id} no es una carga de alto valor.")
        self._exigir_estado("autorizar la carga de alto valor",
                            EstadoServicio.CONFIRMADO, EstadoServicio.UNIDAD_ASIGNADA)
        self._alto_valor_autorizado = True
        self._registrar(f"Carga de alto valor autorizada por {autorizado_por}", autorizado_por)
        self._eventos.append(CargaDeAltoValorAutorizada(orden_id=self.id, autorizado_por=autorizado_por))

    def cancelar(self, solicitado_por: str, motivo: str) -> None:
        """SUPUESTO S-04: cancela un servicio aceptado; registra quién la solicita y el motivo."""
        if not solicitado_por.strip() or not motivo.strip():
            raise ErrorDeDominio("La cancelación debe registrar quién la solicita y el motivo.")
        self._exigir_estado("cancelar el servicio", EstadoServicio.CONFIRMADO, EstadoServicio.UNIDAD_ASIGNADA,
                            EstadoServicio.RECOLECTADO, EstadoServicio.EN_TRANSITO,
                            EstadoServicio.LLEGADA_A_DESTINO)
        self._cancelacion = Cancelacion(solicitado_por, motivo, ahora())
        self._estado = EstadoServicio.CANCELADO
        self._registrar(f"Servicio cancelado a solicitud de {solicitado_por}: {motivo}", solicitado_por)
        self._eventos.append(ServicioCancelado(orden_id=self.id, solicitado_por=solicitado_por, motivo=motivo))

    def registrar_recepcion(self, evidencia: Evidencia, registrado_por: str = "Operador") -> None:
        self._exigir_estado("registrar la recepción", EstadoServicio.UNIDAD_ASIGNADA)
        self._evidencias_recepcion.append(evidencia)
        self._estado = EstadoServicio.RECOLECTADO
        self._registrar("Mercancía recibida y validada en origen", registrado_por)

    def iniciar_traslado(self, registrado_por: str = "Operador") -> None:
        self._exigir_estado("iniciar el traslado", EstadoServicio.RECOLECTADO)
        self._estado = EstadoServicio.EN_TRANSITO
        self._registrar("Traslado iniciado", registrado_por)

    def registrar_llegada_a_destino(self, registrado_por: str = "Operador") -> None:
        self._exigir_estado("registrar la llegada", EstadoServicio.EN_TRANSITO)
        self._estado = EstadoServicio.LLEGADA_A_DESTINO
        self._registrar("Llegada a destino", registrado_por)

    def registrar_entrega(self, destinatario: Destinatario, evidencia: Evidencia,
                          registrado_por: str = "Operador") -> None:
        self._exigir_estado("registrar la entrega", EstadoServicio.LLEGADA_A_DESTINO)
        self._destinatario = destinatario
        self._evidencias_entrega.append(evidencia)
        self._estado = EstadoServicio.ENTREGADO
        self._fecha_entrega = ahora()
        self._registrar(f"Entrega registrada; recibió {destinatario.identificacion}", registrado_por)
        self._eventos.append(EntregaRegistrada(orden_id=self.id, destinatario=destinatario))

    def registrar_incidencia(self, tipo: TipoDeIncidencia, descripcion: str,
                             evidencia: Evidencia | None = None, registrado_por: str = "Operador") -> None:
        """Registra una incidencia sin cambiar el estado: Operaciones decide el siguiente paso."""
        if self._estado in (EstadoServicio.ENTREGADO, EstadoServicio.CANCELADO):
            raise TransicionDeEstadoInvalida(
                f"No se puede registrar una incidencia en estado {self._estado.value}."
            )
        incidencia = Incidencia(len(self._incidencias) + 1, tipo, descripcion, ahora())
        if evidencia is not None:
            incidencia.evidencias.append(evidencia)
        self._incidencias.append(incidencia)
        self._registrar(f"Incidencia {tipo.value}: {descripcion}", registrado_por)
        self._eventos.append(IncidenciaRegistrada(orden_id=self.id, tipo=tipo))

    # ------------------------------ internos ------------------------------
    def _registrar(self, descripcion: str, registrado_por: str) -> None:
        self._historial.append(EntradaDeHistorial(ahora(), descripcion, self._estado, registrado_por))

    def _exigir_estado(self, accion: str, *permitidos: EstadoServicio) -> None:
        if self._estado not in permitidos:
            esperados = " o ".join(e.value for e in permitidos)
            raise TransicionDeEstadoInvalida(
                f"No se puede {accion} en estado {self._estado.value} (se requiere {esperados})."
            )
