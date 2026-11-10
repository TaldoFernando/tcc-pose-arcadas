"""Painel visual local da Etapa 8; importar no console do 3D Slicer.

    import etapa8_painel_visual as visual
    visual.painel()

Folga mínima em Z técnico, em unidades presumidas do STL. Somente cópias de
visualização se deslocam. O ponto analítico permanece no referencial C do
STL canônico carregado, não no referencial bruto do escaneamento.
"""
from math import isfinite, isclose

_aberto = None
_arcadas = ("superior", "inferior")
VERSAO = "1.0"


def _deslocamentos(limites_superior, limites_inferior, folga):
    """Separação simétrica das caixas em Z, sem reduzir folga já existente."""
    if not isfinite(folga) or folga <= 0:
        raise ValueError("Informe uma folga visual positiva, em unidades do STL.")
    sup_min, sup_max = limites_superior[4:6]
    inf_min, inf_max = limites_inferior[4:6]
    if not all(map(isfinite, (sup_min, sup_max, inf_min, inf_max))):
        raise ValueError("A geometria tem limites inválidos.")
    if sup_min > sup_max or inf_min > inf_max:
        raise ValueError("A geometria de uma das arcadas está vazia.")
    sinal = 1 if sup_min + sup_max >= inf_min + inf_max else -1
    distancia = sup_min - inf_max if sinal == 1 else inf_min - sup_max
    deslocamento = sinal * max(0.0, folga - distancia) / 2
    return {"superior": deslocamento, "inferior": -deslocamento}


def _ponto(ponto, dz):
    if len(ponto) != 3 or not all(map(isfinite, ponto)) or not isfinite(dz):
        raise ValueError("Posição ou deslocamento visual inválido.")
    return [float(ponto[0]), float(ponto[1]), float(ponto[2]) + float(dz)]


def _para_canonico(ponto_visual, dz):
    return _ponto(ponto_visual, -dz)


def _para_visual(ponto_canonico, dz):
    return _ponto(ponto_canonico, dz)


def _iguais(a, b):
    return (a is None and b is None) or (
        a is not None and b is not None
        and all(isclose(x, y, rel_tol=0, abs_tol=1e-9) for x, y in zip(a, b))
    )


def _copiar_deslocado(vtk, malha, dz):
    transformacao = vtk.vtkTransform()
    transformacao.Translate(0, 0, dz)
    filtro = vtk.vtkTransformPolyDataFilter()
    filtro.SetTransform(transformacao)
    filtro.SetInputData(malha)
    filtro.SetOutputPointsPrecision(vtk.vtkAlgorithm.DOUBLE_PRECISION)
    filtro.Update()
    copia = vtk.vtkPolyData()
    copia.DeepCopy(filtro.GetOutput())
    return copia


def _posicao_definida(no, indice, estado_definido):
    if no.GetNthControlPointPositionStatus(indice) != estado_definido:
        return None
    ponto = [0.0, 0.0, 0.0]
    no.GetNthControlPointPositionWorld(indice, ponto)
    return ponto


class _Vista:
    def __init__(self, e8, sessao, dialogo, folga, slicer, qt, vtk):
        self.e8, self.sessao = e8, sessao
        self.slicer, self.qt, self.vtk = slicer, qt, vtk
        self.dialogo, self.folga = dialogo, folga
        self.marcas, self.modelos = sessao["marks"], sessao["models"]
        self.definicoes = sessao["definitions"]
        self.definido = slicer.vtkMRMLMarkupsNode.PositionDefined
        self.alvo, self.fechado, self.sincronizando = None, False, False
        self.temporarios, self.observadores, self.botoes = [], [], []
        self.previews, self.pontos_visuais, self.indices, self.combos = {}, {}, {}, {}
        self.propostas_visuais, self.geometrias_visuais = {}, {}
        self.pontos_referencias, self.indices_referencias = {}, {}
        originais = [*self.modelos.values(), self.marcas]
        if sessao.get("hints") is not None:
            originais.append(sessao["hints"])
        if any(no.GetParentTransformNode() is not None for no in originais):
            raise RuntimeError("Abra a sessão no referencial canônico, sem transforms na cena.")
        self._validar_ordem()
        self.displays_originais = [
            (no, no.GetDisplayNode(), no.GetDisplayNode().GetVisibility()) for no in originais
        ]
        self.dz = _deslocamentos(
            self.modelos["superior"].GetPolyData().GetBounds(),
            self.modelos["inferior"].GetPolyData().GetBounds(), folga
        )
        logica = slicer.app.applicationLogic()
        self.interacao, self.selecao = logica.GetInteractionNode(), logica.GetSelectionNode()
        self.markups = slicer.modules.markups.logic()
        self.modo_anterior = self.interacao.GetCurrentInteractionMode()
        self.persistencia_anterior = self.interacao.GetPlaceModePersistence()
        self.lista_anterior = self.selecao.GetActivePlaceNodeID()
        self.classe_anterior = self.selecao.GetActivePlaceNodeClassName()
        try:
            self._criar_vista()
            self._criar_painel()
            self._observar(self.marcas, slicer.vtkMRMLMarkupsNode.PointModifiedEvent, self._originais_mudaram)
            self._observar(self.marcas, slicer.vtkMRMLMarkupsNode.PointPositionUndefinedEvent, self._originais_mudaram)
            for arcada, no in self.pontos_visuais.items():
                self._observar(no, slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
                               lambda caller, event, a=arcada: self._preview_mudou(a))
            for no, display, visivel in self.displays_originais:
                display.SetVisibility(False)
            self.dialogo.connect("finished(int)", lambda result: self.fechar())
        except Exception:
            self.fechar()
            raise

    def _ativa(self):
        if self.fechado or self.e8._SESSION is not self.sessao:
            raise RuntimeError("Este painel pertence a outra sessão ou já foi fechado.")
        if self.marcas.GetScene() is None:
            raise RuntimeError("A sessão foi removida da cena.")
        self._validar_ordem()
        for no in [*self.modelos.values(), *self.previews.values(), *self.pontos_visuais.values(), *self.pontos_referencias.values(), self.clique]:
            if no.GetParentTransformNode() is not None:
                raise RuntimeError("Não aplicar transforms aos modelos ou pontos. Feche e reabra apenas o painel visual.")
        for arcada, (poly, mtime) in self.geometrias_visuais.items():
            atual = self.previews[arcada].GetPolyData()
            if atual != poly or atual.GetMTime() != mtime:
                raise RuntimeError("Geometria da cópia visual modificada; feche e reabra apenas o painel visual.")

    def _validar_ordem(self):
        if self.marcas.GetNumberOfControlPoints() != len(self.definicoes):
            raise RuntimeError("A lista de landmarks não corresponde ao protocolo.")
        for i, lm in enumerate(self.definicoes):
            if self.marcas.GetNthControlPointLabel(i) != lm["label"]:
                raise RuntimeError("Não renomear nem reordenar os landmarks.")

    def _observar(self, no, evento, funcao):
        self.observadores.append((no, no.AddObserver(evento, funcao)))

    def _guardar(self, no):
        self.temporarios.append(no)
        return no

    def _criar_vista(self):
        for arcada in _arcadas:
            origem = self.modelos[arcada]
            modelo = self._guardar(self.slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLModelNode", "E8_VIS_" + self.sessao["ID"] + "_" + arcada))
            modelo.SetAndObservePolyData(_copiar_deslocado(self.vtk, origem.GetPolyData(), self.dz[arcada]))
            modelo.CreateDefaultDisplayNodes()
            modelo.GetDisplayNode().SetColor(*origem.GetDisplayNode().GetColor())
            modelo.GetDisplayNode().SetOpacity(origem.GetDisplayNode().GetOpacity())
            self.previews[arcada] = modelo
            self.geometrias_visuais[arcada] = (modelo.GetPolyData(), modelo.GetPolyData().GetMTime())
            indices = [i for i, lm in enumerate(self.definicoes) if lm["arcada"] == arcada]
            self.indices[arcada] = indices
            pontos = []
            for i in indices:
                p = _posicao_definida(self.marcas, i, self.definido)
                pontos.append((self.definicoes[i]["label"],
                               _para_visual(p, self.dz[arcada]) if p is not None else None))
            no = self._guardar(self.e8._fiducials(
                "E8_VIS_PONTOS_" + arcada, pontos, (1., .65, .1)))
            no.SetFixedNumberOfControlPoints(True)
            self.pontos_visuais[arcada] = no
            if self.sessao.get("hints") is not None:
                hints = self.sessao["hints"]
                pontos_hints = []
                for i in indices:
                    p = _posicao_definida(hints, i, self.definido)
                    pontos_hints.append((self.definicoes[i]["label"],
                                         _para_visual(p, self.dz[arcada]) if p is not None else None))
                self.propostas_visuais[arcada] = self._guardar(self.e8._fiducials(
                    "E8_VIS_PROPOSTAS_" + arcada, pontos_hints, (.55, .55, .55), True))
        import referencias_pendentes as refs
        rows = refs.linhas(self.sessao, self.e8.ROOT)
        state = refs.estado(self.sessao, self.e8.ROOT) if rows else None
        for arcada in _arcadas:
            rr = [r for r in rows if r["arcada"] == arcada]
            if not rr:
                continue
            self.indices_referencias[arcada] = [r["label"] for r in rr]
            points = []
            for r in rr:
                p = state["points"][r["label"]]["position"]
                points.append((r["label"], _para_visual(p, self.dz[arcada]) if p is not None else None))
            node = self._guardar(self.e8._fiducials("E8_VIS_REFERENCIAS_" + arcada, points, (.3, .9, .8)))
            node.SetFixedNumberOfControlPoints(True)
            for k, r in enumerate(rr):
                node.SetNthControlPointLocked(k, not r["habilitada"])
            self.pontos_referencias[arcada] = node
            self._observar(node, self.slicer.vtkMRMLMarkupsNode.PointModifiedEvent,
                           lambda caller, event, a=arcada: self._referencia_preview_mudou(a))
        self.clique = self._guardar(self.slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLMarkupsFiducialNode", "E8_VIS_CLIQUE"))
        self.clique.CreateDefaultDisplayNodes()
        self.clique.SetMaximumNumberOfControlPoints(1)
        self.clique.GetDisplayNode().SetTextScale(0.)
        self._observar(self.clique, self.slicer.vtkMRMLMarkupsNode.PointPositionDefinedEvent, self._clicou)

    def _criar_painel(self):
        layout = self.qt.QVBoxLayout(self.dialogo)
        layout.addWidget(self.qt.QLabel(
            "Folga mínima visual: " + str(self.folga) +
            " unidade(s) do STL. Exportação no referencial C canônico."))
        self.aviso = self.qt.QLabel("Clique em Posicionar 3D e depois sobre a superfície da arcada indicada.")
        self.aviso.setWordWrap(True)
        layout.addWidget(self.aviso)
        scroll = self.qt.QScrollArea()
        scroll.setWidgetResizable(True)
        content = self.qt.QWidget()
        body = self.qt.QVBoxLayout(content)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        grid = self.qt.QGridLayout()
        body.addLayout(grid)
        estados = ["pendente", "aceito", "corrigido", "ausente", "nao_visivel",
                   "nao_aplicavel", "lateralidade_incerta"]
        for linha, lm in enumerate(self.definicoes):
            label = lm["label"]
            title = self.qt.QLabel(label + " · " + lm["arcada"])
            title.setToolTip(lm["definicao_provisoria"] + "\nVista: " + lm.get("vista_referencia", "Conferir em múltiplas vistas.") + "\nAusência: " + lm["ausencia"])
            grid.addWidget(title, linha, 0)
            colocar = self.qt.QPushButton("Posicionar 3D")
            colocar.connect("clicked()", lambda l=label: self._seguro(lambda: self.posicionar(l)))
            grid.addWidget(colocar, linha, 1)
            combo = self.qt.QComboBox()
            combo.addItems(estados)
            review = self.sessao.get("reviews", {}).get(label)
            if review:
                combo.setCurrentIndex(estados.index(review["status"]))
            self.combos[label] = combo
            grid.addWidget(combo, linha, 2)
            confirmar = self.qt.QPushButton("Confirmar ponto")
            confirmar.connect("clicked()", lambda l=label: self._seguro(lambda: self.confirmar(l)))
            grid.addWidget(confirmar, linha, 3)
            self.botoes.extend([colocar, confirmar])
        import referencias_pendentes as refs
        self.referencias_widgets = refs.adicionar_linhas(
            grid, self.sessao, self.e8.ROOT,
            lambda l: self._seguro(lambda: self.posicionar_referencia(l)),
            lambda l, v: self._seguro(lambda: self.confirmar_referencia(l, v)))
        self.dialogo.resize(950, 740)
        cancelar = self.qt.QPushButton("Cancelar posicionamento")
        cancelar.connect("clicked()", lambda: self._seguro(self.cancelar))
        layout.addWidget(cancelar)
        exportar = self.qt.QPushButton("Exportar sessão revisada")
        exportar.connect("clicked()", lambda: self._seguro(self.exportar))
        layout.addWidget(exportar)
        fechar = self.qt.QPushButton("Fechar painel visual e restaurar vista")
        fechar.connect("clicked()", self.dialogo.close)
        layout.addWidget(fechar)

    def _seguro(self, funcao):
        try:
            return funcao()
        except Exception as e:
            self.slicer.util.errorDisplay(str(e))

    def _mostrar(self, somente=None):
        for arcada in _arcadas:
            visivel = somente is None or somente == arcada
            self.previews[arcada].GetDisplayNode().SetVisibility(visivel)
            self.pontos_visuais[arcada].GetDisplayNode().SetVisibility(visivel)
            if arcada in self.pontos_referencias:
                self.pontos_referencias[arcada].GetDisplayNode().SetVisibility(visivel)
            if arcada in self.propostas_visuais:
                self.propostas_visuais[arcada].GetDisplayNode().SetVisibility(visivel)

    def _revisao_pendente(self, indice):
        label = self.definicoes[indice]["label"]
        self.sessao.get("reviews", {}).pop(label, None)
        self.sessao["exported"] = False
        self.combos[label].setCurrentIndex(0)

    def _originais_mudaram(self, caller=None, event=None):
        if self.fechado or self.sincronizando:
            return
        self._ativa()
        self.sincronizando = True
        try:
            for arcada, indices in self.indices.items():
                no = self.pontos_visuais[arcada]
                for k, i in enumerate(indices):
                    p = _posicao_definida(self.marcas, i, self.definido)
                    atual = _posicao_definida(no, k, self.definido)
                    visual = _para_visual(p, self.dz[arcada]) if p is not None else None
                    if _iguais(visual, atual):
                        continue
                    if visual is None:
                        no.UnsetNthControlPointPosition(k)
                    else:
                        no.SetNthControlPointPositionWorld(k, *visual)
        finally:
            self.sincronizando = False

    def _preview_mudou(self, arcada):
        if self.fechado or self.sincronizando:
            return
        self._ativa()
        no = self.pontos_visuais[arcada]
        indices = self.indices[arcada]
        if no.GetNumberOfControlPoints() != len(indices):
            raise RuntimeError("Não adicionar/remover pontos da vista visual.")
        self.sincronizando = True
        try:
            for k, i in enumerate(indices):
                if no.GetNthControlPointLabel(k) != self.definicoes[i]["label"]:
                    raise RuntimeError("Não renomear os pontos da vista visual.")
                visual = _posicao_definida(no, k, self.definido)
                canonico = _para_canonico(visual, self.dz[arcada]) if visual is not None else None
                atual = _posicao_definida(self.marcas, i, self.definido)
                if _iguais(canonico, atual):
                    continue
                if canonico is None:
                    self.marcas.UnsetNthControlPointPosition(i)
                else:
                    self.marcas.SetNthControlPointPositionWorld(i, *canonico)
                self._revisao_pendente(i)
        finally:
            self.sincronizando = False

    def posicionar(self, label):
        self._ativa()
        self.cancelar()
        indice = next(i for i, lm in enumerate(self.definicoes) if lm["label"] == label)
        arcada = self.definicoes[indice]["arcada"]
        self.alvo = (indice, arcada)
        self._mostrar(somente=arcada)
        self.selecao.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
        self.markups.SetActiveListID(self.clique)
        self.interacao.SetPlaceModePersistence(0)
        self.interacao.SetCurrentInteractionMode(self.interacao.Place)
        self.aviso.setText(label + ": clique sobre a superfície da arcada " + arcada + ".")

    def _clicou(self, caller=None, event=None):
        if self.fechado or self.alvo is None or self.sincronizando:
            return
        try:
            self._ativa()
            p = _posicao_definida(self.clique, 0, self.definido)
            if p is None:
                return
            if len(self.alvo) == 3:
                import referencias_pendentes as refs
                _, label, arcada = self.alvo
                refs.posicionar(self.sessao, label, _para_canonico(p, self.dz[arcada]), self.e8.ROOT)
                self._sincronizar_referencias()
                self.referencias_widgets[label]["combo"].setCurrentIndex(0)
            else:
                indice, arcada = self.alvo
                canonico = _para_canonico(p, self.dz[arcada])
                self.marcas.SetNthControlPointPositionWorld(indice, *canonico)
                self._revisao_pendente(indice)
                label = self.definicoes[indice]["label"]
            self.alvo = None
            self._mostrar()
            self.interacao.SetCurrentInteractionMode(self.interacao.ViewTransform)
            self.qt.QTimer.singleShot(0, self.cancelar)
            self.aviso.setText(label + ": ponto posicionado. Inspecione, selecione o estado e confirme.")
        except Exception as e:
            self.cancelar()
            self.slicer.util.errorDisplay(str(e))

    def posicionar_referencia(self, label):
        self._ativa()
        import referencias_pendentes as refs
        row = refs.habilitada(self.sessao, label, self.e8.ROOT)
        self.cancelar()
        self.alvo = ("referencia", label, row["arcada"])
        self._mostrar(somente=row["arcada"])
        self.selecao.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
        self.markups.SetActiveListID(self.clique)
        self.interacao.SetPlaceModePersistence(0)
        self.interacao.SetCurrentInteractionMode(self.interacao.Place)
        self.aviso.setText(label + (": marcação provisória do piloto; clique na superfície pretendida e confirme individualmente." if row["marcacao_provisoria"] else ": posicionamento manual conforme critérios da orientadora."))

    def confirmar_referencia(self, label, status):
        self._ativa()
        import referencias_pendentes as refs
        self.cancelar()
        refs.confirmar(self.sessao, label, status, self.e8.ROOT)
        self._sincronizar_referencias()
        self.aviso.setText(label + ": referência obrigatória do piloto confirmada individualmente.")

    def _sincronizar_referencias(self):
        import referencias_pendentes as refs
        state = refs.estado(self.sessao, self.e8.ROOT)
        self.sincronizando = True
        try:
            for arch, node in self.pontos_referencias.items():
                for k, label in enumerate(self.indices_referencias[arch]):
                    p = state["points"][label]["position"]
                    if p is None:
                        node.UnsetNthControlPointPosition(k)
                    else:
                        node.SetNthControlPointPositionWorld(k, *_para_visual(p, self.dz[arch]))
        finally:
            self.sincronizando = False

    def _referencia_preview_mudou(self, arch):
        if self.fechado or self.sincronizando:
            return
        self._ativa()
        import referencias_pendentes as refs
        state = refs.estado(self.sessao, self.e8.ROOT)
        for k, label in enumerate(self.indices_referencias[arch]):
            visual = _posicao_definida(self.pontos_referencias[arch], k, self.definido)
            p = _para_canonico(visual, self.dz[arch]) if visual is not None else None
            if _iguais(p, state["points"][label]["position"]):
                continue
            refs.habilitada(self.sessao, label, self.e8.ROOT)
            if p is None:
                state["points"][label].update(position=None, review=None)
                self.sessao["exported"] = False
            else:
                refs.posicionar(self.sessao, label, p, self.e8.ROOT)
            self.referencias_widgets[label]["combo"].setCurrentIndex(0)

    def cancelar(self):
        self.alvo = None
        if not self.fechado and self.clique.GetScene() is not None:
            self.clique.RemoveAllControlPoints()
            self.interacao.SetCurrentInteractionMode(self.interacao.ViewTransform)
            self._mostrar()
            if self.marcas.GetScene() is not None:
                self.markups.SetActiveListID(self.marcas)

    def confirmar(self, label):
        self._ativa()
        self.cancelar()
        self.e8.revisar(label, str(self.combos[label].currentText))
        self._originais_mudaram()
        self.aviso.setText(label + ": revisão registrada no referencial C canônico.")

    def exportar(self):
        self._ativa()
        self.cancelar()
        # O exportador original valida revisão, geometria e C; nada é deslocado para exportar.
        sidecar = self.e8.ROOT / "qa" / "visualizacao" / ("{ID}_{avaliador}_{sessao}".format(**self.sessao) + ".json")
        if sidecar.exists():
            raise ValueError("Registro visual desta sessão já existe; não sobrescrever.")
        path = self.e8.exportar()
        try:
            self._registrar_uso(path)
        except OSError as error:
            self.aviso.setText("Sessão exportada, mas o registro visual falhou: " + str(error))
            self.slicer.util.warningDisplay("A sessão foi exportada em C. Falha ao gravar metadados de visualização; informar à coordenação.")
            return path
        self.aviso.setText("Sessão exportada em C canônico. Atualize o acompanhamento.")
        return path

    def _registrar_uso(self, export_path):
        from pathlib import Path
        import datetime, json
        from e8_common import sha
        pasta = self.e8.ROOT / "qa" / "visualizacao"
        pasta.mkdir(parents=True, exist_ok=True)
        identificador = "{ID}_{avaliador}_{sessao}".format(**self.sessao)
        registro = {
            "ID": self.sessao["ID"], "avaliador": self.sessao["avaliador"],
            "sessao": self.sessao["sessao"], "fase": self.sessao["phase"],
            "complemento": "etapa8_painel_visual", "versao": VERSAO,
            "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "folga_minima_visual_unidades_STL": self.folga,
            "deslocamentos_apenas_visualizacao_Z": self.dz,
            "referencial_exportado": "CANONICAL_STL_CARTESIAN",
            "export_json_sha256": sha(Path(export_path)),
            "codigo_complemento_sha256": sha(Path(__file__)),
            "STL_modificados": False, "normalizadores_modificados": False
        }
        target = pasta / (identificador + ".json")
        # Exportação de sessão não é sobrescrita pelo exportador principal.
        with target.open("x") as f:
            json.dump(registro, f, ensure_ascii=False, indent=2)

    def fechar(self):
        global _aberto
        if self.fechado:
            return
        self.fechado = True
        self.alvo = None
        for no, tag in self.observadores:
            no.RemoveObserver(tag)
        self.observadores.clear()
        for no, display, visivel in self.displays_originais:
            if no.GetScene() is not None:
                display.SetVisibility(visivel)
        for no in reversed(self.temporarios):
            if no.GetScene() is not None:
                self.slicer.mrmlScene.RemoveNode(no)
        self.temporarios.clear()
        if self.lista_anterior and self.slicer.mrmlScene.GetNodeByID(self.lista_anterior):
            self.selecao.SetReferenceActivePlaceNodeID(self.lista_anterior)
            if self.classe_anterior:
                self.selecao.SetReferenceActivePlaceNodeClassName(self.classe_anterior)
        self.interacao.SetPlaceModePersistence(self.persistencia_anterior)
        self.interacao.SetCurrentInteractionMode(self.modo_anterior)
        for b in self.botoes:
            b.setEnabled(False)
        if _aberto is self:
            _aberto = None


def painel(folga=1.0):
    """Abre a visualização da sessão atual, sem reiniciar ou descartar pontos."""
    global _aberto
    import slicer, qt, vtk
    import slicer_markups as e8
    # Atualizar só a função de data importada, sem recarregar e8 nem apagar _SESSION.
    import e8_common as common
    if not hasattr(common, "study_timezone"):
        from importlib import reload
        common = reload(common)
    common.study_timezone()
    e8.local_today = common.local_today
    folga = float(folga)
    if not hasattr(slicer, "mrmlScene"):
        raise RuntimeError("Executar no console Python do 3D Slicer.")
    if e8._SESSION is None:
        raise ValueError("Abra antes uma sessão com e8.iniciar(). Não reinicie uma sessão pendente.")
    if _aberto is not None:
        if _aberto.sessao is e8._SESSION and isclose(_aberto.folga, folga):
            _aberto.dialogo.show()
            _aberto.dialogo.activateWindow()
            return _aberto.dialogo
        fechar()
    if e8._SESSION["phase"] != "pilot":
        from e8_common import protocol
        protocol(e8.ROOT)
        from pathlib import Path
        from e8_common import load, sha
        approved = load(e8.ROOT / "protocolo_validado.json")
        if approved.get("code_sha256", {}).get("etapa8_painel_visual.py") != sha(Path(__file__)):
            raise ValueError("O complemento precisa constar do congelamento humano antes da coleta principal. Valide-o no piloto.")
    if not isfinite(folga) or folga <= 0:
        raise ValueError("Folga visual deve ser positiva e finita.")
    antigo = e8._SESSION.get("dialog")
    if antigo is not None:
        antigo.close()
    dialogo = qt.QDialog(slicer.util.mainWindow())
    dialogo.setWindowTitle("Etapa 8 · " + e8._SESSION["ID"] + " · arcadas separadas")
    _aberto = _Vista(e8, e8._SESSION, dialogo, folga, slicer, qt, vtk)
    e8._SESSION["dialog"] = dialogo
    dialogo.show()
    slicer.util.resetThreeDViews()
    return dialogo


def fechar():
    """Restaura a vista; as marcações canônicas feitas continuam na sessão."""
    if _aberto is not None:
        vista = _aberto
        vista.fechar()
        vista.dialogo.close()


def reabrir():
    """Atualiza código do painel preservando a sessão e seus nós existentes."""
    import importlib
    import slicer_markups as e8
    fechar()
    session = e8._SESSION
    if session is None:
        raise ValueError("Abra antes o piloto; nenhuma sessão foi descartada.")
    if session.get("dialog") is not None:
        session["dialog"].close()
    try:
        importlib.reload(e8)
    finally:
        e8._SESSION = session
    return painel()


def abrir_template():
    """Atualiza os módulos e abre o template manual sem descartar sessão pendente."""
    import importlib
    import e8_common as common
    import slicer_markups as e8
    fechar()
    session = e8._SESSION
    if session and not session.get("exported"):
        raise ValueError("Exporte a sessão atual antes de abrir o template. Nenhum ponto foi descartado.")
    common = importlib.reload(common)
    try:
        importlib.reload(e8)
    finally:
        e8._SESSION = session
    common.protocol()
    identifier = common.load(common.ROOT / "plano.json")["template_ID"]
    e8.iniciar(identifier, "A1", "T1", modo="manual")
    return painel()
