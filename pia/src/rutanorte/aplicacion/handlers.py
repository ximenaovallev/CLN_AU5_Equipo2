"""Service Layer: cada handler coordina un caso de uso.

Recibe la solicitud, obtiene los objetos, invoca el comportamiento del dominio, pide la
persistencia y devuelve un resultado. Las reglas del negocio viven en el dominio.
"""
from __future__ import annotations

from uuid import uuid4

from ..dominio.comunes import ErrorDeDominio
from ..dominio.orden_de_servicio import OrdenDeServicio
from ..dominio.servicios import AsignadorDeRecursos, AutoridadDeCancelacion
from ..dominio.valores import Horario
from .comandos import (
    AsignarRecursosCommand,
    AutorizarCargaDeAltoValorCommand,
    CancelarServicioCommand,
    ConsultarEstadoDelServicioQuery,
    ConsultarIndicadoresQuery,
    GenerarOrdenDeServicioCommand,
    RegistrarEntregaCommand,
    ResponderCotizacionCommand,
    RespuestaDelCliente,
)
from .dto import EstadoDelServicioDTO, IndicadoresDTO, Resultado
from .puertos import IConsultaDeServicios, IPublicadorDeEventos, IUnitOfWork


class ResponderCotizacionHandler:
    """CU-01 Responder cotización."""

    def __init__(self, uow: IUnitOfWork, publicador: IPublicadorDeEventos):
        self._uow, self._publicador = uow, publicador

    def handle(self, cmd: ResponderCotizacionCommand) -> Resultado:
        try:
            with self._uow as uow:
                cotizacion = uow.cotizaciones.obtener_por_id(cmd.cotizacion_id)
                if cmd.respuesta is RespuestaDelCliente.ACEPTA:
                    cotizacion.aceptar()
                else:
                    cotizacion.rechazar()
                uow.cotizaciones.guardar(cotizacion)
                uow.confirmar()
                eventos = cotizacion.extraer_eventos()
        except ErrorDeDominio as error:
            return Resultado.fallo(str(error))
        self._publicador.publicar(eventos)
        return Resultado.ok(f"Cotización {cotizacion.estado.value}.", estado=cotizacion.estado.value)


class GenerarOrdenDeServicioHandler:
    """CU-02 Generar orden de servicio."""

    def __init__(self, uow: IUnitOfWork, publicador: IPublicadorDeEventos):
        self._uow, self._publicador = uow, publicador

    def handle(self, cmd: GenerarOrdenDeServicioCommand) -> Resultado:
        try:
            with self._uow as uow:
                cotizacion = uow.cotizaciones.obtener_por_id(cmd.cotizacion_id)
                orden = OrdenDeServicio.generar_desde(
                    id=str(uuid4()), cotizacion=cotizacion, ruta=cmd.ruta,
                    horario_recoleccion=Horario(cmd.horario_recoleccion),
                )
                uow.ordenes.guardar(orden)
                uow.confirmar()
                eventos = orden.extraer_eventos()
        except ErrorDeDominio as error:
            return Resultado.fallo(str(error))
        self._publicador.publicar(eventos)
        return Resultado.ok("Orden de servicio generada.", orden_id=orden.id)


class AutorizarCargaDeAltoValorHandler:
    """CU-07 Autorizar carga de alto valor (SUPUESTO S-02)."""

    def __init__(self, uow: IUnitOfWork, publicador: IPublicadorDeEventos):
        self._uow, self._publicador = uow, publicador

    def handle(self, cmd: AutorizarCargaDeAltoValorCommand) -> Resultado:
        try:
            with self._uow as uow:
                orden = uow.ordenes.obtener_por_id(cmd.orden_id)
                orden.autorizar_alto_valor(cmd.autorizado_por)
                uow.ordenes.guardar(orden)
                uow.confirmar()
                eventos = orden.extraer_eventos()
        except ErrorDeDominio as error:
            return Resultado.fallo(str(error))
        self._publicador.publicar(eventos)
        return Resultado.ok("Carga de alto valor autorizada.")


class CancelarServicioHandler:
    """CU-06 Cancelar servicio (SUPUESTO S-04): registra quién la solicita y el motivo."""

    def __init__(self, uow: IUnitOfWork, publicador: IPublicadorDeEventos, autoridad: AutoridadDeCancelacion):
        self._uow, self._publicador, self._autoridad = uow, publicador, autoridad

    def handle(self, cmd: CancelarServicioCommand) -> Resultado:
        try:
            self._autoridad.verificar(cmd.rol_que_autoriza)
            with self._uow as uow:
                orden = uow.ordenes.obtener_por_id(cmd.orden_id)
                orden.cancelar(cmd.solicitado_por, cmd.motivo)
                uow.ordenes.guardar(orden)
                uow.confirmar()
                eventos = orden.extraer_eventos()
        except ErrorDeDominio as error:
            return Resultado.fallo(str(error))
        self._publicador.publicar(eventos)
        return Resultado.ok("Servicio cancelado.", estado=orden.estado_actual().value)


class AsignarRecursosHandler:
    """CU-03 Asignar unidad y operador (también reasigna si el operador cambia)."""

    def __init__(self, uow: IUnitOfWork, publicador: IPublicadorDeEventos, asignador: AsignadorDeRecursos):
        self._uow, self._publicador, self._asignador = uow, publicador, asignador

    def handle(self, cmd: AsignarRecursosCommand) -> Resultado:
        try:
            with self._uow as uow:
                orden = uow.ordenes.obtener_por_id(cmd.orden_id)
                unidad = uow.unidades.obtener_por_id(cmd.unidad_id)
                operador = uow.operadores.obtener_por_id(cmd.operador_id)
                asignacion = self._asignador.validar_y_crear(orden, unidad, operador)  # regla G2
                orden.asignar_recursos(asignacion, registrado_por="Operaciones")
                uow.ordenes.guardar(orden)
                uow.confirmar()
                eventos = orden.extraer_eventos()
        except ErrorDeDominio as error:  # el `with` ya revirtió la transacción
            return Resultado.fallo(str(error))
        self._publicador.publicar(eventos)
        return Resultado.ok("Unidad y operador asignados.", estado=orden.estado_actual().value)


class RegistrarEntregaHandler:
    """CU-04 Registrar entrega o incidencia en destino."""

    def __init__(self, uow: IUnitOfWork, publicador: IPublicadorDeEventos):
        self._uow, self._publicador = uow, publicador

    def handle(self, cmd: RegistrarEntregaCommand) -> Resultado:
        try:
            with self._uow as uow:
                orden = uow.ordenes.obtener_por_id(cmd.orden_id)
                if cmd.incidencia is None:
                    if cmd.destinatario is None:
                        return Resultado.fallo("La entrega requiere identificar a quien recibe.")
                    orden.registrar_entrega(cmd.destinatario, cmd.evidencia)
                else:
                    orden.registrar_incidencia(cmd.incidencia, cmd.descripcion_incidencia, cmd.evidencia)
                uow.ordenes.guardar(orden)
                uow.confirmar()
                eventos = orden.extraer_eventos()
        except ErrorDeDominio as error:
            return Resultado.fallo(str(error))
        self._publicador.publicar(eventos)
        return Resultado.ok("Registro completado.", estado=orden.estado_actual().value)


class ConsultarEstadoDelServicioHandler:
    """CU-05 Consultar estado del servicio (Query, sin cargar el agregado)."""

    def __init__(self, consulta: IConsultaDeServicios):
        self._consulta = consulta

    def handle(self, query: ConsultarEstadoDelServicioQuery) -> EstadoDelServicioDTO:
        return self._consulta.estado_del_servicio(query.orden_id)


class ConsultarIndicadoresHandler:
    """Query de indicadores históricos para Operaciones."""

    def __init__(self, consulta: IConsultaDeServicios):
        self._consulta = consulta

    def handle(self, query: ConsultarIndicadoresQuery) -> IndicadoresDTO:
        return self._consulta.indicadores(query.desde, query.hasta)
