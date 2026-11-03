"""Raíz de composición: único lugar donde se eligen las implementaciones concretas."""
from __future__ import annotations

from dataclasses import dataclass

from .aplicacion.handlers import (
    AsignarRecursosHandler,
    AutorizarCargaDeAltoValorHandler,
    CancelarServicioHandler,
    ConsultarEstadoDelServicioHandler,
    ConsultarIndicadoresHandler,
    GenerarOrdenDeServicioHandler,
    RegistrarEntregaHandler,
    ResponderCotizacionHandler,
)
from .dominio.servicios import AsignadorDeRecursos, AutoridadDeCancelacion, PoliticaDeCapacidadEmpresa
from .dominio.valores import PoliticaDeConservacion
from .infraestructura.en_memoria import (
    AlmacenEnMemoria,
    EnMemoriaConsultaDeServicios,
    EnMemoriaUnitOfWork,
    PublicadorDeEventosEnMemoria,
)


@dataclass
class Aplicacion:
    almacen: AlmacenEnMemoria
    publicador: PublicadorDeEventosEnMemoria
    responder_cotizacion: ResponderCotizacionHandler
    generar_orden: GenerarOrdenDeServicioHandler
    asignar_recursos: AsignarRecursosHandler
    registrar_entrega: RegistrarEntregaHandler
    autorizar_alto_valor: AutorizarCargaDeAltoValorHandler
    cancelar_servicio: CancelarServicioHandler
    politica_de_conservacion: PoliticaDeConservacion
    consultar_estado: ConsultarEstadoDelServicioHandler
    consultar_indicadores: ConsultarIndicadoresHandler


def construir_aplicacion(
    peso_maximo_kg: float | None = None,
    volumen_maximo_m3: float | None = None,
    dias_de_conservacion: int | None = None,
    roles_que_cancelan: frozenset[str] = frozenset({"Operaciones"}),
) -> Aplicacion:
    """Los parámetros son los SUPUESTOS pendientes de validar (S-01, S-03, S-04): ver docs/05."""
    almacen = AlmacenEnMemoria()
    uow = EnMemoriaUnitOfWork(almacen)
    publicador = PublicadorDeEventosEnMemoria()
    consulta = EnMemoriaConsultaDeServicios(almacen)
    asignador = AsignadorDeRecursos(PoliticaDeCapacidadEmpresa(peso_maximo_kg, volumen_maximo_m3))
    return Aplicacion(
        almacen=almacen,
        publicador=publicador,
        responder_cotizacion=ResponderCotizacionHandler(uow, publicador),
        generar_orden=GenerarOrdenDeServicioHandler(uow, publicador),
        asignar_recursos=AsignarRecursosHandler(uow, publicador, asignador),
        registrar_entrega=RegistrarEntregaHandler(uow, publicador),
        autorizar_alto_valor=AutorizarCargaDeAltoValorHandler(uow, publicador),
        cancelar_servicio=CancelarServicioHandler(uow, publicador, AutoridadDeCancelacion(roles_que_cancelan)),
        politica_de_conservacion=PoliticaDeConservacion(dias_de_conservacion),
        consultar_estado=ConsultarEstadoDelServicioHandler(consulta),
        consultar_indicadores=ConsultarIndicadoresHandler(consulta),
    )
